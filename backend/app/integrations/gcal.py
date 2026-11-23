import json
import time
from datetime import datetime
from typing import Callable
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from app.errors import ProviderError

TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar}/events"
SCOPE = "https://www.googleapis.com/auth/calendar"
Transport = Callable[[str, str, dict, bytes | None], tuple[int, bytes]]


def auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode({"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state})
    return f"{AUTH_URL}?{query}"


def _form(values: dict) -> bytes:
    return urlencode(values).encode()


def exchange_code(client_id: str, client_secret: str, code: str, redirect_uri: str, transport: Transport) -> str:
    body = _form({"code": code, "client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri, "grant_type": "authorization_code"})
    status, payload = transport("POST", TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, body)
    data = json.loads(payload or b"{}")
    if status != 200 or "refresh_token" not in data:
        raise ProviderError(f"Google did not return a refresh token (HTTP {status})")
    return data["refresh_token"]


class GoogleCalendar:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str, calendar_id: str, timezone: str, transport: Transport, clock: Callable[[], float] = time.time):
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._calendar_id = calendar_id
        self._tz = timezone
        self._transport = transport
        self._clock = clock
        self._access_token = ""
        self._expires_at = 0.0

    @staticmethod
    def from_env(env, transport: Transport):
        keys = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
        if not all(env.get(k) for k in keys):
            return None
        return GoogleCalendar(env["GOOGLE_CLIENT_ID"], env["GOOGLE_CLIENT_SECRET"], env["GOOGLE_REFRESH_TOKEN"], env.get("GOOGLE_CALENDAR_ID", "primary"), env.get("USER_TIMEZONE", "Asia/Kolkata"), transport)

    def _aware(self, value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=ZoneInfo(self._tz))

    def _token(self) -> str:
        if self._access_token and self._clock() < self._expires_at - 60:
            return self._access_token
        body = _form({"client_id": self._client_id, "client_secret": self._client_secret, "refresh_token": self._refresh_token, "grant_type": "refresh_token"})
        status, payload = self._transport("POST", TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, body)
        data = json.loads(payload or b"{}")
        if status != 200 or "access_token" not in data:
            raise ProviderError(f"Google token refresh failed (HTTP {status})")
        self._access_token = data["access_token"]
        self._expires_at = self._clock() + int(data.get("expires_in", 3600))
        return self._access_token

    def _call(self, method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
        headers = {"Authorization": f"Bearer {self._token()}", "Content-Type": "application/json"}
        status, payload = self._transport(method, url, headers, json.dumps(body).encode() if body is not None else None)
        return status, json.loads(payload or b"{}")

    def _events_url(self) -> str:
        return EVENTS_URL.format(calendar=quote(self._calendar_id, safe=""))

    def _local(self, value: str | None) -> str | None:
        if not value or "T" not in value:
            return value
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ZoneInfo(self._tz)).isoformat()

    def _summarise(self, item: dict) -> dict:
        start, end = item.get("start", {}), item.get("end", {})
        return {"id": item.get("id"), "summary": item.get("summary", "(no title)"), "start": self._local(start.get("dateTime")) or start.get("date"), "end": self._local(end.get("dateTime")) or end.get("date"), "all_day": "date" in start, "link": item.get("htmlLink")}

    def list_events(self, time_min: datetime, time_max: datetime) -> list[dict]:
        query = urlencode({"timeMin": self._aware(time_min).isoformat(), "timeMax": self._aware(time_max).isoformat(), "singleEvents": "true", "orderBy": "startTime", "maxResults": 50})
        status, data = self._call("GET", f"{self._events_url()}?{query}")
        if status != 200:
            raise ProviderError(f"Google Calendar list failed (HTTP {status})")
        return [self._summarise(item) for item in data.get("items", [])]

    def create_event(self, event_id: str, summary: str, start: datetime, end: datetime, description: str) -> dict:
        body = {"id": event_id, "summary": summary, "description": description, "start": {"dateTime": self._aware(start).isoformat(), "timeZone": self._tz}, "end": {"dateTime": self._aware(end).isoformat(), "timeZone": self._tz}}
        status, data = self._call("POST", self._events_url(), body)
        if status == 409:
            status, data = self._call("GET", f"{self._events_url()}/{event_id}")
            if status != 200:
                raise ProviderError(f"Google Calendar duplicate lookup failed (HTTP {status})")
            return {**self._summarise(data), "duplicate": True}
        if status != 200:
            raise ProviderError(f"Google Calendar create failed (HTTP {status})")
        return {**self._summarise(data), "duplicate": False}
