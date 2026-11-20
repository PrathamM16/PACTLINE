import hashlib
import unittest
from datetime import date

from app.domain.tools import ToolContext, ToolRegistry
from app.errors import ProviderError
from app.storage import open_store

OWNER = ToolContext("family", "pratham", "owner", "pratham@example.com")
OUTSIDER = ToolContext("stranger", "eve", "owner", "eve@example.com")
TODAY = date(2026, 11, 20)
CLASH = {"id": "e1", "summary": "Team sync", "start": "2026-11-21T10:30:00+05:30", "end": "2026-11-21T11:30:00+05:30", "all_day": False, "link": None}
HOLIDAY = {"id": "e2", "summary": "Holiday", "start": "2026-11-21", "end": "2026-11-22", "all_day": True, "link": None}
BOOKING = {"title": "Bank visit", "start": "2026-11-21T10:00:00", "end": "2026-11-21T11:00:00", "description": "", "ignore_conflicts": False}


class FakeCalendar:
    def __init__(self, events=None, fail=False):
        self.events = events or []
        self.fail = fail
        self.created = []

    def list_events(self, start, end):
        if self.fail:
            raise ProviderError("Google Calendar list failed (HTTP 500)")
        return list(self.events)

    def create_event(self, event_id, summary, start, end, description):
        if self.fail:
            raise ProviderError("Google Calendar create failed (HTTP 403)")
        self.created.append((event_id, summary, start, end))
        return {"id": event_id, "summary": summary, "link": f"https://calendar.example/{event_id}", "duplicate": False}


def registry(calendar):
    return ToolRegistry(open_store("sqlite:///:memory:"), today=lambda: TODAY, calendar=calendar)


class UnavailableCalendarTest(unittest.TestCase):
    def test_listing_without_calendar_reports_unavailable(self):
        result = registry(None).call("listCalendarEvents", OWNER, {"date_from": "2026-11-21", "date_to": "2026-11-21"})
        self.assertEqual(result["error"], "integration_unavailable")

    def test_booking_without_calendar_creates_no_approval(self):
        reg = registry(None)
        reg.call("createCalendarEvent", OWNER, BOOKING)
        self.assertEqual(reg.pending_approvals(OWNER), [])

    def test_booking_without_calendar_reports_unavailable(self):
        self.assertEqual(registry(None).call("createCalendarEvent", OWNER, BOOKING)["error"], "integration_unavailable")


class ListEventsTest(unittest.TestCase):
    def test_events_come_from_calendar_provider(self):
        result = registry(FakeCalendar([CLASH])).call("listCalendarEvents", OWNER, {"date_from": "2026-11-21", "date_to": "2026-11-21"})
        self.assertEqual(result["data"][0]["summary"], "Team sync")

    def test_provider_failure_is_reported_not_hidden(self):
        result = registry(FakeCalendar(fail=True)).call("listCalendarEvents", OWNER, {"date_from": "2026-11-21", "date_to": "2026-11-21"})
        self.assertEqual(result["error"], "provider_error")

    def test_invalid_date_is_rejected(self):
        result = registry(FakeCalendar()).call("listCalendarEvents", OWNER, {"date_from": "tomorrow", "date_to": "2026-11-21"})
        self.assertEqual(result["error"], "invalid_request")


class ConflictDetectionTest(unittest.TestCase):
    def test_clash_is_reported_before_any_approval(self):
        result = registry(FakeCalendar([CLASH])).call("createCalendarEvent", OWNER, BOOKING)
        self.assertEqual(result["status"], "conflict")

    def test_clash_lists_conflicting_event(self):
        result = registry(FakeCalendar([CLASH])).call("createCalendarEvent", OWNER, BOOKING)
        self.assertEqual(result["conflicts"][0]["summary"], "Team sync")

    def test_clash_creates_no_pending_approval(self):
        reg = registry(FakeCalendar([CLASH]))
        reg.call("createCalendarEvent", OWNER, BOOKING)
        self.assertEqual(reg.pending_approvals(OWNER), [])

    def test_all_day_event_is_not_a_clash(self):
        result = registry(FakeCalendar([HOLIDAY])).call("createCalendarEvent", OWNER, BOOKING)
        self.assertEqual(result["status"], "awaiting_user_approval")

    def test_ignore_conflicts_proceeds_to_approval(self):
        result = registry(FakeCalendar([CLASH])).call("createCalendarEvent", OWNER, {**BOOKING, "ignore_conflicts": True})
        self.assertEqual(result["status"], "awaiting_user_approval")

    def test_end_before_start_is_rejected(self):
        result = registry(FakeCalendar()).call("createCalendarEvent", OWNER, {**BOOKING, "end": "2026-11-21T09:00:00"})
        self.assertEqual(result["error"], "invalid_request")

    def test_invalid_datetime_is_rejected(self):
        result = registry(FakeCalendar()).call("createCalendarEvent", OWNER, {**BOOKING, "start": "10 o clock"})
        self.assertEqual(result["error"], "invalid_request")


class EventCreationTest(unittest.TestCase):
    def setUp(self):
        self.calendar = FakeCalendar()
        self.reg = registry(self.calendar)
        self.approval_id = self.reg.call("createCalendarEvent", OWNER, BOOKING)["approval_id"]

    def test_nothing_is_created_before_approval(self):
        self.assertEqual(self.calendar.created, [])

    def test_approval_creates_the_event(self):
        self.reg.decide(OWNER, self.approval_id, True)
        self.assertEqual(self.calendar.created[0][1], "Bank visit")

    def test_event_id_is_derived_from_approval_id(self):
        self.reg.decide(OWNER, self.approval_id, True)
        self.assertEqual(self.calendar.created[0][0], hashlib.sha1(self.approval_id.encode()).hexdigest())

    def test_result_carries_provider_link(self):
        outcome = self.reg.decide(OWNER, self.approval_id, True)
        self.assertTrue(outcome["result"]["data"]["link"].startswith("https://calendar.example/"))

    def test_rejection_creates_nothing(self):
        self.reg.decide(OWNER, self.approval_id, False)
        self.assertEqual(self.calendar.created, [])

    def test_provider_failure_marks_approval_failed(self):
        self.calendar.fail = True
        self.assertEqual(self.reg.decide(OWNER, self.approval_id, True)["status"], "failed")

    def test_provider_failure_is_visible_to_agent_via_status_tool(self):
        self.calendar.fail = True
        self.reg.decide(OWNER, self.approval_id, True)
        status = self.reg.call("getApprovalStatus", OWNER, {"approval_id": self.approval_id})
        self.assertEqual(status["data"]["result"]["error"], "provider_error")

    def test_failed_booking_is_audited(self):
        self.calendar.fail = True
        self.reg.decide(OWNER, self.approval_id, True)
        self.assertIn("provider_error", [e["outcome"] for e in self.reg.store.audit_list("family")])


class BriefingTest(unittest.TestCase):
    def briefing(self, reg, ctx=OWNER):
        return reg.call("getDailyBriefing", ctx, {"unused": ""})["data"]

    def test_briefing_reports_calendar_not_connected(self):
        self.assertEqual(self.briefing(registry(None))["calendar"], {"connected": False})

    def test_briefing_includes_real_calendar_events(self):
        self.assertEqual(self.briefing(registry(FakeCalendar([CLASH])))["calendar"]["events"][0]["summary"], "Team sync")

    def test_briefing_reports_calendar_error_instead_of_hiding_it(self):
        self.assertIn("error", self.briefing(registry(FakeCalendar(fail=True)))["calendar"])

    def test_reminder_creation_stores_recipient_email(self):
        reg = registry(None)
        args = {"text": "call", "remind_at": "2026-11-21T09:00:00", "for_person": ""}
        reg.decide(OWNER, reg.call("createReminder", OWNER, args)["approval_id"], True)
        self.assertEqual(reg.store.list_records("reminder", "family")[0]["recipient_email"], "pratham@example.com")

    def test_follow_ups_list_waiting_reminders(self):
        reg = registry(None)
        args = {"text": "call", "remind_at": "2026-11-21T09:00:00", "for_person": ""}
        reg.decide(OWNER, reg.call("createReminder", OWNER, args)["approval_id"], True)
        self.assertEqual(len(self.briefing(reg)["follow_ups"]["reminders_waiting"]), 1)

    def test_follow_ups_flag_overdue_task(self):
        reg = registry(None)
        approval = reg.call("createTask", OWNER, {"title": "late", "assignee": "pratham", "due_date": "2026-11-18"})["approval_id"]
        reg.decide(OWNER, approval, True)
        self.assertEqual(len(self.briefing(reg)["follow_ups"]["overdue_tasks"]), 1)

    def test_follow_ups_flag_unassigned_task(self):
        reg = registry(None)
        reg.decide(OWNER, reg.call("createTask", OWNER, {"title": "x", "assignee": "", "due_date": ""})["approval_id"], True)
        self.assertEqual(len(self.briefing(reg)["follow_ups"]["unassigned_tasks"]), 1)

    def test_briefing_lists_shopping_lists(self):
        reg = registry(None)
        reg.decide(OWNER, reg.call("createShoppingList", OWNER, {"name": "Weekend"})["approval_id"], True)
        self.assertEqual(self.briefing(reg)["shopping_lists"][0]["name"], "Weekend")

    def test_other_workspace_briefing_has_no_foreign_reminders(self):
        reg = registry(None)
        args = {"text": "call", "remind_at": "2026-11-21T09:00:00", "for_person": ""}
        reg.decide(OWNER, reg.call("createReminder", OWNER, args)["approval_id"], True)
        self.assertEqual(self.briefing(reg, OUTSIDER)["reminders"], [])


if __name__ == "__main__":
    unittest.main()
