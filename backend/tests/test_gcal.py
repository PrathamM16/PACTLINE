import json
import unittest
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from app.errors import ProviderError
from app.integrations.gcal import GoogleCalendar, SCOPE, auth_url, exchange_code

START = datetime(2026, 11, 21, 10, 0)
END = datetime(2026, 11, 21, 11, 0)
EVENT_OK = json.dumps({"id": "abc", "summary": "Standup", "htmlLink": "https://calendar.example/e/abc", "start": {"dateTime": "2026-11-21T10:00:00+05:30"}, "end": {"dateTime": "2026-11-21T11:00:00+05:30"}}).encode()
TOKEN_OK = json.dumps({"access_token": "at-1", "expires_in": 3600}).encode()


class Recorder:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        return self.responses.pop(0)


def calendar(responses, clock=lambda: 1000.0):
    transport = Recorder(responses)
    return GoogleCalendar("cid", "secret", "refresh", "primary", "Asia/Kolkata", transport, clock), transport


class AuthUrlTest(unittest.TestCase):
    def setUp(self):
        self.query = parse_qs(urlparse(auth_url("cid", "http://127.0.0.1:8765", "st")).query)

    def test_scope_is_calendar_scope_from_google_docs(self):
        self.assertEqual(self.query["scope"], [SCOPE])

    def test_offline_access_is_requested_for_refresh_token(self):
        self.assertEqual(self.query["access_type"], ["offline"])

    def test_consent_prompt_is_forced(self):
        self.assertEqual(self.query["prompt"], ["consent"])

    def test_state_is_included(self):
        self.assertEqual(self.query["state"], ["st"])


class ExchangeCodeTest(unittest.TestCase):
    def test_refresh_token_is_returned(self):
        transport = Recorder([(200, json.dumps({"refresh_token": "rt"}).encode())])
        self.assertEqual(exchange_code("cid", "sec", "code", "http://x", transport), "rt")

    def test_missing_refresh_token_raises(self):
        with self.assertRaises(ProviderError):
            exchange_code("cid", "sec", "code", "http://x", Recorder([(200, b"{}")]))

    def test_http_error_raises(self):
        with self.assertRaises(ProviderError):
            exchange_code("cid", "sec", "code", "http://x", Recorder([(400, b"{}")]))


class TokenTest(unittest.TestCase):
    def test_refresh_request_uses_refresh_token_grant(self):
        cal, transport = calendar([(200, TOKEN_OK), (200, json.dumps({"items": []}).encode())])
        cal.list_events(START, END)
        self.assertIn(b"grant_type=refresh_token", transport.calls[0][3])

    def test_access_token_is_cached_between_calls(self):
        cal, transport = calendar([(200, TOKEN_OK), (200, b'{"items": []}'), (200, b'{"items": []}')])
        cal.list_events(START, END)
        cal.list_events(START, END)
        self.assertEqual(len(transport.calls), 3)

    def test_expired_token_is_refreshed_again(self):
        now = [1000.0]
        cal, transport = calendar([(200, TOKEN_OK), (200, b'{"items": []}'), (200, TOKEN_OK), (200, b'{"items": []}')], lambda: now[0])
        cal.list_events(START, END)
        now[0] = 9999.0
        cal.list_events(START, END)
        self.assertEqual(len(transport.calls), 4)

    def test_token_failure_raises_provider_error(self):
        cal, _ = calendar([(401, b"{}")])
        with self.assertRaises(ProviderError):
            cal.list_events(START, END)

    def test_bearer_header_is_sent_to_calendar_api(self):
        cal, transport = calendar([(200, TOKEN_OK), (200, b'{"items": []}')])
        cal.list_events(START, END)
        self.assertEqual(transport.calls[1][2]["Authorization"], "Bearer at-1")


class ListEventsTest(unittest.TestCase):
    def test_query_expands_recurring_events_in_start_order(self):
        cal, transport = calendar([(200, TOKEN_OK), (200, b'{"items": []}')])
        cal.list_events(START, END)
        self.assertIn("singleEvents=true", transport.calls[1][1])

    def test_naive_times_get_configured_offset(self):
        cal, transport = calendar([(200, TOKEN_OK), (200, b'{"items": []}')])
        cal.list_events(START, END)
        self.assertIn("2026-11-21T10%3A00%3A00%2B05%3A30", transport.calls[1][1])

    def test_all_day_event_is_flagged(self):
        body = json.dumps({"items": [{"id": "1", "summary": "Holiday", "start": {"date": "2026-11-21"}, "end": {"date": "2026-11-22"}}]}).encode()
        cal, _ = calendar([(200, TOKEN_OK), (200, body)])
        self.assertTrue(cal.list_events(START, END)[0]["all_day"])

    def test_timed_event_is_not_flagged_all_day(self):
        body = json.dumps({"items": [{"id": "1", "summary": "Call", "start": {"dateTime": "2026-11-21T10:00:00+05:30"}, "end": {"dateTime": "2026-11-21T11:00:00+05:30"}}]}).encode()
        cal, _ = calendar([(200, TOKEN_OK), (200, body)])
        self.assertFalse(cal.list_events(START, END)[0]["all_day"])

    def test_utc_times_are_converted_to_configured_timezone(self):
        body = json.dumps({"items": [{"id": "1", "summary": "Call", "start": {"dateTime": "2026-11-21T03:30:00Z"}, "end": {"dateTime": "2026-11-21T04:00:00Z"}}]}).encode()
        cal, _ = calendar([(200, TOKEN_OK), (200, body)])
        event = cal.list_events(START, END)[0]
        self.assertEqual((event["start"], event["end"]), ("2026-11-21T09:00:00+05:30", "2026-11-21T09:30:00+05:30"))

    def test_list_failure_raises_provider_error(self):
        cal, _ = calendar([(200, TOKEN_OK), (500, b"{}")])
        with self.assertRaises(ProviderError):
            cal.list_events(START, END)


class CreateEventTest(unittest.TestCase):
    def create(self, responses):
        cal, transport = calendar([(200, TOKEN_OK)] + responses)
        return cal.create_event("a1b2c3d4e5", "Standup", START, END, "notes"), transport

    def test_created_event_returns_link_from_google_response(self):
        result, _ = self.create([(200, EVENT_OK)])
        self.assertEqual(result["link"], "https://calendar.example/e/abc")

    def test_created_event_is_not_marked_duplicate(self):
        result, _ = self.create([(200, EVENT_OK)])
        self.assertFalse(result["duplicate"])

    def test_body_carries_custom_event_id(self):
        _, transport = self.create([(200, EVENT_OK)])
        self.assertEqual(json.loads(transport.calls[1][3])["id"], "a1b2c3d4e5")

    def test_body_carries_time_zone_and_offset(self):
        _, transport = self.create([(200, EVENT_OK)])
        start = json.loads(transport.calls[1][3])["start"]
        self.assertEqual((start["timeZone"], start["dateTime"]), ("Asia/Kolkata", "2026-11-21T10:00:00+05:30"))

    def test_conflict_409_returns_existing_event_as_duplicate(self):
        result, _ = self.create([(409, b"{}"), (200, EVENT_OK)])
        self.assertTrue(result["duplicate"])

    def test_failed_duplicate_lookup_raises(self):
        cal, _ = calendar([(200, TOKEN_OK), (409, b"{}"), (404, b"{}")])
        with self.assertRaises(ProviderError):
            cal.create_event("a1b2c3d4e5", "x", START, END, "")

    def test_create_failure_raises_provider_error(self):
        cal, _ = calendar([(200, TOKEN_OK), (403, b"{}")])
        with self.assertRaises(ProviderError):
            cal.create_event("a1b2c3d4e5", "x", START, END, "")


class FromEnvTest(unittest.TestCase):
    def test_missing_refresh_token_means_not_configured(self):
        self.assertIsNone(GoogleCalendar.from_env({"GOOGLE_CLIENT_ID": "a", "GOOGLE_CLIENT_SECRET": "b"}, Recorder([])))

    def test_complete_env_builds_client(self):
        env = {"GOOGLE_CLIENT_ID": "a", "GOOGLE_CLIENT_SECRET": "b", "GOOGLE_REFRESH_TOKEN": "c"}
        self.assertIsInstance(GoogleCalendar.from_env(env, Recorder([])), GoogleCalendar)


if __name__ == "__main__":
    unittest.main()
