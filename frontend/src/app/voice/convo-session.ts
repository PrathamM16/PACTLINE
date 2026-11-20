import AgoraRTC, { IAgoraRTCClient, IMicrophoneAudioTrack } from 'agora-rtc-sdk-ng';
import { RTMClient } from 'agora-rtm-sdk';
import { AgoraVoiceAI, AgoraVoiceAIEvents, TranscriptHelperMode } from 'agora-agent-client-toolkit';
import { api } from '../core/auth';

export type AgentState = 'IDLE' | 'CONNECTING' | 'LISTENING' | 'THINKING' | 'SPEAKING' | 'ERROR' | 'DISCONNECTED';

export interface TranscriptLine {
  uid: string;
  turnId: number;
  text: string;
  final: boolean;
}

export interface SessionHandlers {
  onState(state: AgentState): void;
  onTranscript(lines: TranscriptLine[]): void;
  onError(message: string): void;
}

interface TokenResponse {
  channel: string;
  agentUid: number;
  rtcToken: string;
  rtmToken: string;
  appId: string;
}

const STATE_MAP: Record<string, AgentState> = {
  idle: 'IDLE',
  listening: 'LISTENING',
  thinking: 'THINKING',
  speaking: 'SPEAKING',
  silent: 'LISTENING',
};

async function post<T>(path: string, body: object): Promise<T> {
  return api<T>(path, { body });
}

export class ConvoSession {
  private rtc?: IAgoraRTCClient;
  private rtm?: RTMClient;
  private mic?: IMicrophoneAudioTrack;
  private api?: AgoraVoiceAI;
  private agentId?: string;
  private agentUid = '';
  private channel = '';

  constructor(private readonly handlers: SessionHandlers) {}

  async start(): Promise<void> {
    this.handlers.onState('CONNECTING');
    const userUid = Math.floor(Math.random() * 1_000_000) + 1000;
    try {
      const token = await post<TokenResponse>('/api/voice/token', { user_uid: userUid });
      this.channel = token.channel;
      this.agentUid = String(token.agentUid);

      this.rtc = AgoraRTC.createClient({ mode: 'rtc', codec: 'vp8' });
      this.rtc.on('user-published', async (user, mediaType) => {
        await this.rtc!.subscribe(user, mediaType);
        if (mediaType === 'audio') {
          user.audioTrack?.play();
        }
      });
      await this.rtc.join(token.appId, token.channel, token.rtcToken, userUid);
      this.mic = await AgoraRTC.createMicrophoneAudioTrack();
      await this.rtc.publish([this.mic]);

      this.rtm = new RTMClient(token.appId, String(userUid));
      await this.rtm.login({ token: token.rtmToken });
      await this.rtm.subscribe(token.channel);

      this.api = await AgoraVoiceAI.init({
        rtcEngine: this.rtc,
        rtmConfig: { rtmEngine: this.rtm },
        renderMode: TranscriptHelperMode.TEXT,
      });
      this.api.on(AgoraVoiceAIEvents.TRANSCRIPT_UPDATED, (items: any[]) => {
        this.handlers.onTranscript(items.map((i) => ({ uid: String(i.uid), turnId: i.turn_id, text: i.text, final: i.status !== 0 })));
      });
      this.api.on(AgoraVoiceAIEvents.AGENT_STATE_CHANGED, (_agent: string, event: { state: unknown }) => {
        this.handlers.onState(STATE_MAP[String(event.state).toLowerCase()] ?? 'LISTENING');
      });
      this.api.subscribeMessage(token.channel);

      const started = await post<{ agentId: string }>('/api/voice/start', { channel: token.channel });
      this.agentId = started.agentId;
      this.handlers.onState('LISTENING');
    } catch (error) {
      await this.cleanup();
      this.handlers.onError(error instanceof Error ? error.message : 'Voice session failed');
      this.handlers.onState('ERROR');
    }
  }

  async interrupt(): Promise<void> {
    await this.api?.interrupt(this.agentUid);
  }

  async stop(): Promise<void> {
    try {
      if (this.agentId) {
        await post('/api/voice/stop', { agent_id: this.agentId });
      }
    } catch (error) {
      this.handlers.onError(error instanceof Error ? error.message : 'Stop failed');
    } finally {
      await this.cleanup();
      this.handlers.onState('DISCONNECTED');
    }
  }

  private async cleanup(): Promise<void> {
    try {
      const toolkit = this.api as unknown as { unsubscribe?: () => void; destroy?: () => void } | undefined;
      toolkit?.unsubscribe?.();
      toolkit?.destroy?.();
    } catch {
      this.api = undefined;
    }
    this.mic?.stop();
    this.mic?.close();
    await this.rtc?.leave().catch(() => undefined);
    await this.rtm?.logout().catch(() => undefined);
    this.api = undefined;
    this.mic = undefined;
    this.rtc = undefined;
    this.rtm = undefined;
    this.agentId = undefined;
  }
}