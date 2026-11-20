import unittest
from datetime import date

from app.domain.commitments import CommitmentLedger, CommitmentStatus, ConfirmationStatus

WORKSPACE = "family"
CONVERSATION = "conv-1"
FRIDAY = date(2026, 11, 20)
THURSDAY = date(2026, 11, 19)


def reload(ledger, item):
    return ledger.get(item.id, WORKSPACE)


def build_ledger_with_venue_commitment():
    ledger = CommitmentLedger()
    item = ledger.propose("asha", "book the venue", FRIDAY, CONVERSATION, WORKSPACE, "I will book the venue by Friday", "asha")
    return ledger, item


class CommitmentLedgerTest(unittest.TestCase):
    def test_new_commitment_is_only_suggested(self):
        _, item = build_ledger_with_venue_commitment()
        self.assertEqual(item.confirmation, ConfirmationStatus.SUGGESTED)

    def test_new_commitment_is_not_ready_for_execution(self):
        ledger, item = build_ledger_with_venue_commitment()
        self.assertFalse(ledger.is_ready_for_execution(item))

    def test_conflicting_deadline_marks_commitment_disputed(self):
        ledger, item = build_ledger_with_venue_commitment()
        ledger.dispute(item.id, WORKSPACE, "ravi", THURSDAY)
        self.assertEqual(reload(ledger, item).confirmation, ConfirmationStatus.DISPUTED)

    def test_conflict_is_listed_for_workspace(self):
        ledger, item = build_ledger_with_venue_commitment()
        ledger.dispute(item.id, WORKSPACE, "ravi", THURSDAY)
        self.assertEqual([c.id for c in ledger.conflicts(WORKSPACE)], [item.id])

    def test_same_deadline_is_not_a_dispute(self):
        ledger, item = build_ledger_with_venue_commitment()
        ledger.dispute(item.id, WORKSPACE, "ravi", FRIDAY)
        self.assertEqual(ledger.conflicts(WORKSPACE), [])

    def test_disputed_commitment_cannot_be_confirmed(self):
        ledger, item = build_ledger_with_venue_commitment()
        ledger.dispute(item.id, WORKSPACE, "ravi", THURSDAY)
        with self.assertRaises(ValueError):
            ledger.confirm(item.id, WORKSPACE, "asha")

    def test_resolution_applies_agreed_deadline(self):
        ledger, item = build_ledger_with_venue_commitment()
        ledger.dispute(item.id, WORKSPACE, "ravi", THURSDAY)
        ledger.resolve(item.id, WORKSPACE, "asha", THURSDAY)
        self.assertEqual(reload(ledger, item).deadline, THURSDAY)

    def test_resolution_records_who_confirmed(self):
        ledger, item = build_ledger_with_venue_commitment()
        ledger.dispute(item.id, WORKSPACE, "ravi", THURSDAY)
        ledger.resolve(item.id, WORKSPACE, "asha", THURSDAY)
        self.assertEqual(reload(ledger, item).confirmed_by, ["asha"])

    def test_resolution_preserves_agreement_history(self):
        ledger, item = build_ledger_with_venue_commitment()
        ledger.dispute(item.id, WORKSPACE, "ravi", THURSDAY)
        ledger.resolve(item.id, WORKSPACE, "asha", THURSDAY)
        self.assertEqual([h.action for h in reload(ledger, item).history], ["proposed", "disputed", "resolved"])

    def test_resolved_commitment_is_ready_for_execution(self):
        ledger, item = build_ledger_with_venue_commitment()
        ledger.dispute(item.id, WORKSPACE, "ravi", THURSDAY)
        ledger.resolve(item.id, WORKSPACE, "asha", THURSDAY)
        self.assertTrue(ledger.is_ready_for_execution(reload(ledger, item)))

    def test_other_workspace_cannot_read_commitment(self):
        ledger, item = build_ledger_with_venue_commitment()
        with self.assertRaises(PermissionError):
            ledger.get(item.id, "someone-else")

    def test_overdue_lists_pending_past_deadline(self):
        ledger, item = build_ledger_with_venue_commitment()
        self.assertEqual([c.id for c in ledger.overdue(WORKSPACE, date(2026, 11, 21))], [item.id])

    def test_completed_commitment_is_no_longer_pending(self):
        ledger, item = build_ledger_with_venue_commitment()
        ledger.complete(item.id, WORKSPACE, "asha")
        self.assertEqual(ledger.pending(WORKSPACE), [])

    def test_completion_sets_completed_status(self):
        ledger, item = build_ledger_with_venue_commitment()
        ledger.complete(item.id, WORKSPACE, "asha")
        self.assertEqual(reload(ledger, item).status, CommitmentStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
