import os
import tempfile
import unittest
from datetime import date

from app.domain.tools import ToolContext, ToolRegistry
from app.storage import open_store

OWNER = ToolContext("family", "pratham", "owner")
MEMBER = ToolContext("family", "asha", "member")
VIEWER = ToolContext("family", "guest", "viewer")
OUTSIDER = ToolContext("stranger", "eve", "owner")
TODAY = date(2026, 11, 20)


def registry():
    return ToolRegistry(open_store("sqlite:///:memory:"), today=lambda: TODAY)


def task_args(**overrides):
    values = {"title": "Book hotel", "assignee": "", "due_date": ""}
    values.update(overrides)
    return values


def request_task(reg, ctx=OWNER, call_id=""):
    return reg.call("createTask", ctx, task_args(), call_id)


def create_task(reg):
    approval_id = request_task(reg)["approval_id"]
    return reg.decide(OWNER, approval_id, True)["result"]["data"]


def listed(reg, ctx=OWNER):
    return reg.call("listTasks", ctx, {"assignee": ""})["data"]


class ApprovalGateTest(unittest.TestCase):
    def test_write_tool_returns_awaiting_approval(self):
        self.assertEqual(request_task(registry())["status"], "awaiting_user_approval")

    def test_write_tool_changes_nothing_before_approval(self):
        reg = registry()
        request_task(reg)
        self.assertEqual(listed(reg), [])

    def test_approval_executes_the_action(self):
        reg = registry()
        create_task(reg)
        self.assertEqual(len(listed(reg)), 1)

    def test_rejection_executes_nothing(self):
        reg = registry()
        reg.decide(OWNER, request_task(reg)["approval_id"], False)
        self.assertEqual(listed(reg), [])

    def test_rejected_status_is_reported_to_agent(self):
        reg = registry()
        approval_id = request_task(reg)["approval_id"]
        reg.decide(OWNER, approval_id, False)
        status = reg.call("getApprovalStatus", OWNER, {"approval_id": approval_id})
        self.assertEqual(status["data"]["status"], "rejected")

    def test_pending_status_is_reported_to_agent(self):
        reg = registry()
        approval_id = request_task(reg)["approval_id"]
        status = reg.call("getApprovalStatus", OWNER, {"approval_id": approval_id})
        self.assertEqual(status["data"]["status"], "pending")

    def test_executed_status_carries_real_result(self):
        reg = registry()
        approval_id = request_task(reg)["approval_id"]
        reg.decide(OWNER, approval_id, True)
        status = reg.call("getApprovalStatus", OWNER, {"approval_id": approval_id})
        self.assertEqual(status["data"]["result"]["data"]["title"], "Book hotel")

    def test_approval_cannot_be_decided_twice(self):
        reg = registry()
        approval_id = request_task(reg)["approval_id"]
        reg.decide(OWNER, approval_id, True)
        with self.assertRaises(ValueError):
            reg.decide(OWNER, approval_id, True)

    def test_double_approval_creates_only_one_task(self):
        reg = registry()
        approval_id = request_task(reg)["approval_id"]
        reg.decide(OWNER, approval_id, True)
        try:
            reg.decide(OWNER, approval_id, True)
        except ValueError:
            pass
        self.assertEqual(len(listed(reg)), 1)

    def test_llm_cannot_self_approve_by_passing_a_flag(self):
        reg = registry()
        reg.call("createTask", OWNER, {**task_args(), "user_confirmed": True})
        self.assertEqual(listed(reg), [])

    def test_member_cannot_decide_another_users_approval(self):
        reg = registry()
        approval_id = request_task(reg, OWNER)["approval_id"]
        with self.assertRaises(PermissionError):
            reg.decide(MEMBER, approval_id, True)

    def test_owner_can_decide_a_members_approval(self):
        reg = registry()
        approval_id = request_task(reg, MEMBER)["approval_id"]
        self.assertEqual(reg.decide(OWNER, approval_id, True)["status"], "executed")

    def test_viewer_cannot_request_writes(self):
        self.assertEqual(request_task(registry(), VIEWER)["error"], "forbidden")

    def test_other_workspace_cannot_decide_approval(self):
        reg = registry()
        approval_id = request_task(reg)["approval_id"]
        with self.assertRaises(KeyError):
            reg.decide(OUTSIDER, approval_id, True)

    def test_pending_approvals_are_listed_for_workspace(self):
        reg = registry()
        request_task(reg)
        self.assertEqual(len(reg.pending_approvals(OWNER)), 1)


class ToolDispatchTest(unittest.TestCase):
    def test_unknown_tool_is_rejected(self):
        self.assertEqual(registry().call("formatDisk", OWNER, {})["error"], "unknown_tool")

    def test_tool_name_lookup_ignores_case(self):
        self.assertTrue(registry().call("LISTTASKS", OWNER, {"assignee": ""})["ok"])

    def test_missing_arguments_are_reported(self):
        self.assertIn("assignee", registry().call("createTask", OWNER, {"title": "x"})["missing"])

    def test_wrong_argument_type_is_rejected(self):
        self.assertEqual(registry().call("createTask", OWNER, task_args(title=5))["error"], "invalid_request")

    def test_oversized_argument_is_rejected(self):
        self.assertEqual(registry().call("createTask", OWNER, task_args(title="x" * 1001))["error"], "invalid_request")

    def test_invalid_date_is_rejected_before_approval_is_created(self):
        reg = registry()
        reg.call("createTask", OWNER, task_args(due_date="next friday"))
        self.assertEqual(reg.pending_approvals(OWNER), [])

    def test_unknown_task_id_reports_not_found(self):
        reg = registry()
        approval_id = reg.call("completeTask", OWNER, {"task_id": "missing"})["approval_id"]
        self.assertEqual(reg.decide(OWNER, approval_id, True)["status"], "failed")

    def test_empty_optional_assignee_becomes_none(self):
        self.assertIsNone(create_task(registry())["assignee"])


class IdempotencyTest(unittest.TestCase):
    def test_repeated_call_id_returns_same_approval(self):
        reg = registry()
        first = request_task(reg, call_id="call-1")["approval_id"]
        second = request_task(reg, call_id="call-1")["approval_id"]
        self.assertEqual(first, second)

    def test_repeated_call_id_creates_one_pending_approval(self):
        reg = registry()
        request_task(reg, call_id="call-1")
        request_task(reg, call_id="call-1")
        self.assertEqual(len(reg.pending_approvals(OWNER)), 1)

    def test_same_call_id_in_another_workspace_is_independent(self):
        reg = registry()
        request_task(reg, OWNER, "call-1")
        other = request_task(reg, OUTSIDER, "call-1")
        self.assertEqual(other["status"], "awaiting_user_approval")

    def test_other_workspace_does_not_receive_cached_result(self):
        reg = registry()
        first = request_task(reg, OWNER, "call-1")["approval_id"]
        other = request_task(reg, OUTSIDER, "call-1")["approval_id"]
        self.assertNotEqual(first, other)


class WorkspaceIsolationTest(unittest.TestCase):
    def test_other_workspace_cannot_see_tasks(self):
        reg = registry()
        create_task(reg)
        self.assertEqual(listed(reg, OUTSIDER), [])

    def test_other_workspace_cannot_complete_task(self):
        reg = registry()
        task_id = create_task(reg)["id"]
        approval_id = reg.call("completeTask", OUTSIDER, {"task_id": task_id})["approval_id"]
        self.assertEqual(reg.decide(OUTSIDER, approval_id, True)["status"], "failed")

    def test_task_stays_pending_after_foreign_completion_attempt(self):
        reg = registry()
        task_id = create_task(reg)["id"]
        approval_id = reg.call("completeTask", OUTSIDER, {"task_id": task_id})["approval_id"]
        reg.decide(OUTSIDER, approval_id, True)
        self.assertEqual(listed(reg)[0]["status"], "pending")


class CommitmentFlowTest(unittest.TestCase):
    def setUp(self):
        self.reg = registry()
        args = {"owner": "asha", "description": "book venue", "deadline": "2026-11-20", "evidence": "I will book the venue by Friday"}
        approval_id = self.reg.call("createCommitment", OWNER, args)["approval_id"]
        self.commitment_id = self.reg.decide(OWNER, approval_id, True)["result"]["data"]["id"]
        self.dispute_args = {"commitment_id": self.commitment_id, "actor": "ravi", "claimed_deadline": "2026-11-19"}

    def test_dispute_marks_commitment_disputed(self):
        result = self.reg.call("raiseDeadlineDisagreement", OWNER, self.dispute_args)
        self.assertEqual(result["data"]["confirmation"], "disputed")

    def test_dispute_does_not_change_deadline(self):
        result = self.reg.call("raiseDeadlineDisagreement", OWNER, self.dispute_args)
        self.assertEqual(result["data"]["deadline"], "2026-11-20")

    def test_resolution_requires_approval_and_changes_nothing_first(self):
        args = {"commitment_id": self.commitment_id, "actor": "asha", "agreed_deadline": "2026-11-19"}
        self.reg.call("resolveDeadline", OWNER, args)
        self.assertEqual(self.reg.call("listCommitments", OWNER, {"owner": ""})["data"][0]["deadline"], "2026-11-20")

    def test_approved_resolution_sets_agreed_deadline(self):
        args = {"commitment_id": self.commitment_id, "actor": "asha", "agreed_deadline": "2026-11-19"}
        approval_id = self.reg.call("resolveDeadline", OWNER, args)["approval_id"]
        self.assertEqual(self.reg.decide(OWNER, approval_id, True)["result"]["data"]["deadline"], "2026-11-19")

    def test_briefing_lists_disagreement(self):
        self.reg.call("raiseDeadlineDisagreement", OWNER, self.dispute_args)
        self.assertEqual(len(self.reg.call("getDailyBriefing", OWNER, {"unused": ""})["data"]["deadline_disagreements"]), 1)

    def test_briefing_lists_pending_approvals(self):
        request_task(self.reg)
        self.assertEqual(len(self.reg.call("getDailyBriefing", OWNER, {"unused": ""})["data"]["pending_approvals"]), 1)

    def test_other_workspace_cannot_dispute_commitment(self):
        result = self.reg.call("raiseDeadlineDisagreement", OUTSIDER, self.dispute_args)
        self.assertEqual(result["error"], "invalid_request")


class ShoppingAndMemoryTest(unittest.TestCase):
    def test_item_is_added_with_assignee(self):
        reg = registry()
        list_id = reg.decide(OWNER, reg.call("createShoppingList", OWNER, {"name": "Weekend"})["approval_id"], True)["result"]["data"]["id"]
        add = reg.call("addShoppingItem", OWNER, {"list_id": list_id, "item": "fruits", "quantity": "", "assignee": "pratham"})
        reg.decide(OWNER, add["approval_id"], True)
        self.assertEqual(reg.call("getShoppingList", OWNER, {"list_id": list_id})["data"]["items"][0]["assignee"], "pratham")

    def test_preference_appears_in_briefing_after_approval(self):
        reg = registry()
        reg.decide(OWNER, reg.call("savePreference", OWNER, {"key": "meetings", "value": "after 10 AM"})["approval_id"], True)
        self.assertEqual(reg.call("getDailyBriefing", OWNER, {"unused": ""})["data"]["preferences"], {"meetings": "after 10 AM"})

    def test_preference_is_not_visible_in_other_workspace(self):
        reg = registry()
        reg.decide(OWNER, reg.call("savePreference", OWNER, {"key": "meetings", "value": "after 10 AM"})["approval_id"], True)
        self.assertEqual(reg.call("getDailyBriefing", OUTSIDER, {"unused": ""})["data"]["preferences"], {})

    def test_new_reminder_is_pending_never_sent(self):
        reg = registry()
        args = {"text": "call", "remind_at": "2026-11-21T09:00:00", "for_person": ""}
        result = reg.decide(OWNER, reg.call("createReminder", OWNER, args)["approval_id"], True)
        self.assertEqual(result["result"]["data"]["delivery"], "pending")

    def test_invalid_reminder_time_is_rejected(self):
        args = {"text": "call", "remind_at": "tomorrow", "for_person": ""}
        self.assertEqual(registry().call("createReminder", OWNER, args)["error"], "invalid_request")


class AuditTest(unittest.TestCase):
    def test_approval_request_is_audited(self):
        reg = registry()
        request_task(reg)
        self.assertEqual(reg.store.audit_list("family")[0]["outcome"], "approval_requested")

    def test_executed_decision_is_audited(self):
        reg = registry()
        create_task(reg)
        self.assertIn("executed", [e["outcome"] for e in reg.store.audit_list("family")])

    def test_forbidden_attempt_is_audited(self):
        reg = registry()
        request_task(reg, VIEWER)
        self.assertEqual(reg.store.audit_list("family")[0]["outcome"], "forbidden")


class RestartPersistenceTest(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.addCleanup(os.remove, self.path)
        self.url = f"sqlite:///{self.path}"
        first = ToolRegistry(open_store(self.url), today=lambda: TODAY)
        create_task(first)
        request_task(first)
        first.store.db.close()

    def reopen(self):
        registry_after_restart = ToolRegistry(open_store(self.url), today=lambda: TODAY)
        self.addCleanup(registry_after_restart.store.db.close)
        return registry_after_restart

    def test_approved_task_survives_restart(self):
        self.assertEqual(len(listed(self.reopen())), 1)

    def test_pending_approval_survives_restart(self):
        self.assertEqual(len(self.reopen().pending_approvals(OWNER)), 1)


if __name__ == "__main__":
    unittest.main()
