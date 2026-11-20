import base64
import json
import os
import time
import urllib.error
import urllib.request

JOIN_URL = "https://api.agora.io/api/conversational-ai-agent/v2/projects/{app_id}/join"
LEAVE_URL = "https://api.agora.io/api/conversational-ai-agent/v2/projects/{app_id}/agents/{agent_id}/leave"
MURF_STREAM_URL = "wss://global.api.murf.ai/v1/speech/stream-input"
AGENT_UID = 123456
TOKEN_TTL_SECONDS = 3600

SYSTEM_PROMPT = (
    "You are PACTLINE, a warm, concise voice assistant that turns conversations into commitments and actions. "
    "Speak in short natural sentences. Never invent tasks, events, builds or results. "
    "Only state that something was done after a tool result or getApprovalStatus confirms it. "
    "Tools that change data only create a pending approval. Say exactly what you requested, ask the user to press Approve in the app, then call getApprovalStatus and report the real outcome. "
    "Never claim an action happened while its approval is pending or rejected. "
    "If two people disagree about a deadline, call raiseDeadlineDisagreement, ask which date they agree on, and never choose a date yourself. "
    "Call getDailyBriefing when asked to plan the day or what is pending, and use only what it returns. "
    "If createCalendarEvent returns status conflict, nothing was booked: describe the clash and ask whether to book anyway or choose another time. "
    "Reminders are emailed later: only say a reminder was sent if getDailyBriefing lists it under reminders_sent. "
    "If any tool returns integration_unavailable or provider_error, say so plainly and offer a sensible alternative. "
    "Times are in the user's local time zone. The user may speak English, Hindi or Hinglish; reply in the language they use. "
    "For tool arguments that are optional, pass an empty string."
)


class AgoraNotConfigured(Exception):
    pass


class AgoraRequestError(Exception):
    pass


def _env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise AgoraNotConfigured(f"{name} is not set")
    return value


def build_tokens(channel: str, uid: int) -> dict:
    from agora_token_builder import RtcTokenBuilder, RtmTokenBuilder

    app_id = _env("AGORA_APP_ID")
    certificate = _env("AGORA_APP_CERTIFICATE")
    expire_at = int(time.time()) + TOKEN_TTL_SECONDS
    rtc = RtcTokenBuilder.buildTokenWithUid(app_id, certificate, channel, uid, role=1, privilegeExpiredTs=expire_at)
    rtm = RtmTokenBuilder.buildToken(app_id, certificate, str(uid), role=1, privilegeExpiredTs=expire_at)
    return {"rtcToken": rtc, "rtmToken": rtm, "expireAt": expire_at, "appId": app_id}


def tool_specs(public_base_url: str, definitions: list) -> list[dict]:
    specs = []
    for tool in definitions:
        body = {"tool_call_id": "{{tool_call_id}}"}
        body.update({name: "{{args." + name + "}}" for name in tool.parameters["properties"]})
        specs.append({
            "type": "function",
            "function": {"name": tool.name, "description": tool.description, "parameters": tool.parameters},
            "execution": {"mode": "sync"},
            "server": {
                "method": "POST",
                "url": f"{public_base_url.rstrip('/')}/tools/{tool.name}",
                "headers": {"Authorization": "{{template_variables.tool_auth}}", "Content-Type": "application/json"},
                "body": body,
                "timeout_ms": 10000,
            },
        })
    return specs


def build_join_payload(channel: str, agent_token: str, user_uid: int, tool_token: str, tools: list[dict], settings: dict) -> dict:
    return {
        "name": f"pactline-{channel}",
        "properties": {
            "channel": channel,
            "token": agent_token,
            "agent_rtc_uid": str(AGENT_UID),
            "remote_rtc_uids": [str(user_uid)],
            "enable_string_uid": False,
            "idle_timeout": 60,
            "advanced_features": {"enable_rtm": True, "enable_tools": True},
            "asr": {"language": settings["asr_language"]},
            "llm": {
                "url": settings["llm_url"],
                "api_key": settings["llm_api_key"],
                "system_messages": [{"role": "system", "content": SYSTEM_PROMPT}],
                "greeting_message": "Hi, I'm PACTLINE. What should we plan?",
                "failure_message": "Sorry, I hit a problem. Could you say that again?",
                "max_history": 32,
                "params": {"model": settings["llm_model"]},
                "template_variables": {"tool_auth": "Bearer " + tool_token},
                "tools": tools,
            },
            "tts": {
                "vendor": "murf",
                "params": {
                    "api_key": settings["murf_api_key"],
                    "base_url": MURF_STREAM_URL,
                    "voiceId": settings["murf_voice_id"],
                    "locale": settings["murf_locale"],
                    "rate": 0,
                    "pitch": 0,
                    "model": settings["murf_model"],
                    "sample_rate": 24000,
                },
            },
            "parameters": {"data_channel": "rtm", "enable_error_message": True, "enable_metrics": True},
        },
    }


def load_settings() -> dict:
    return {
        "llm_url": os.environ.get("LLM_URL", "https://api.openai.com/v1/chat/completions"),
        "llm_api_key": _env("LLM_API_KEY"),
        "llm_model": _env("LLM_MODEL"),
        "murf_api_key": _env("MURF_API_KEY"),
        "murf_voice_id": os.environ.get("MURF_VOICE_ID", "Matthew"),
        "murf_locale": os.environ.get("MURF_LOCALE", "en-US"),
        "murf_model": os.environ.get("MURF_MODEL", "FALCON"),
        "asr_language": os.environ.get("ASR_LANGUAGE", "en-US"),
    }


def _auth_header() -> str:
    raw = f"{_env('AGORA_CUSTOMER_ID')}:{_env('AGORA_CUSTOMER_SECRET')}"
    return "Basic " + base64.b64encode(raw.encode()).decode()


def _post(url: str, body: dict | None) -> dict:
    data = json.dumps(body).encode() if body is not None else b""
    request = urllib.request.Request(url, data=data, method="POST", headers={"Authorization": _auth_header(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        raise AgoraRequestError(f"HTTP {error.code}: {error.read().decode(errors='replace')[:300]}")


def start_agent(payload: dict) -> dict:
    return _post(JOIN_URL.format(app_id=_env("AGORA_APP_ID")), payload)


def stop_agent(agent_id: str) -> dict:
    return _post(LEAVE_URL.format(app_id=_env("AGORA_APP_ID"), agent_id=agent_id), None)
