import { Component, OnDestroy, signal } from '@angular/core';
import { ApprovalsComponent } from '../core/approvals.component';
import { BriefingComponent } from '../core/briefing.component';
import { ConvoSession, AgentState, TranscriptLine } from './convo-session';

@Component({
  selector: 'app-voice-room',
  standalone: true,
  imports: [ApprovalsComponent, BriefingComponent],
  template: `
    <h2>Voice room</h2>
    <div class="card">
      <p>Agent state: <strong>{{ state() }}</strong></p>
      @if (error()) { <p class="error">{{ error() }}</p> }
      <button (click)="start()" [disabled]="busy()">Start</button>
      <button (click)="interrupt()" [disabled]="state() !== 'SPEAKING'">Interrupt</button>
      <button (click)="stop()" [disabled]="!busy()">End</button>
    </div>
    <div class="card">
      <h3>Live transcript</h3>
      @for (line of lines(); track line.uid + '-' + line.turnId) {
        <p><span class="muted">{{ line.uid === agentUid ? 'PACTLINE' : 'You' }}:</span> {{ line.text }}@if (!line.final) { … }</p>
      } @empty {
        <p class="muted">Nothing said yet.</p>
      }
    </div>
    <app-approvals />
    <app-briefing />
  `,
})
export class VoiceRoomComponent implements OnDestroy {
  readonly agentUid = '123456';
  readonly state = signal<AgentState>('IDLE');
  readonly lines = signal<TranscriptLine[]>([]);
  readonly error = signal('');
  private readonly session = new ConvoSession({
    onState: (value) => this.state.set(value),
    onTranscript: (value) => this.lines.set(value),
    onError: (message) => this.error.set(message),
  });

  busy(): boolean {
    return this.state() !== 'IDLE' && this.state() !== 'DISCONNECTED' && this.state() !== 'ERROR';
  }

  start(): void {
    this.error.set('');
    this.lines.set([]);
    void this.session.start();
  }

  interrupt(): void {
    void this.session.interrupt();
  }

  stop(): void {
    void this.session.stop();
  }

  ngOnDestroy(): void {
    void this.session.stop();
  }
}
