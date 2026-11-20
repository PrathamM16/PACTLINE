import unittest

from app.domain.approval import ApprovalGate, Risk, classify, is_explicit_approval, requires_approval


class RiskClassificationTest(unittest.TestCase):
    def test_reading_calendar_is_low_risk(self):
        self.assertEqual(classify("retrieve_calendar_events"), Risk.LOW)

    def test_creating_task_is_medium_risk(self):
        self.assertEqual(classify("create_task"), Risk.MEDIUM)

    def test_creating_jenkins_job_is_high_risk(self):
        self.assertEqual(classify("create_jenkins_job"), Risk.HIGH)

    def test_unknown_tool_defaults_to_high_risk(self):
        self.assertEqual(classify("format_disk"), Risk.HIGH)

    def test_low_risk_tool_needs_no_approval(self):
        self.assertFalse(requires_approval("retrieve_commitments"))

    def test_medium_risk_tool_needs_approval(self):
        self.assertTrue(requires_approval("create_calendar_event"))


class ExplicitApprovalTest(unittest.TestCase):
    def test_plain_yes_is_accepted(self):
        self.assertTrue(is_explicit_approval("Yes."))

    def test_go_ahead_is_accepted(self):
        self.assertTrue(is_explicit_approval("go ahead"))

    def test_hedged_yes_is_rejected(self):
        self.assertFalse(is_explicit_approval("yes maybe"))

    def test_negation_is_rejected(self):
        self.assertFalse(is_explicit_approval("do not approve"))

    def test_ambiguous_phrase_is_rejected(self):
        self.assertFalse(is_explicit_approval("sounds interesting"))

    def test_empty_utterance_is_rejected(self):
        self.assertFalse(is_explicit_approval(""))


class ApprovalGateTest(unittest.TestCase):
    def setUp(self):
        self.gate = ApprovalGate()
        self.request = self.gate.request("create_jenkins_job", "web-ci", {"branch": "develop"}, False, "pratham")

    def test_pending_request_is_not_approved(self):
        self.assertFalse(self.gate.is_approved(self.request.id, "create_jenkins_job", "web-ci"))

    def test_approved_request_matches_tool_and_resource(self):
        self.gate.decide(self.request.id, "pratham", True)
        self.assertTrue(self.gate.is_approved(self.request.id, "create_jenkins_job", "web-ci"))

    def test_approval_does_not_transfer_to_other_resource(self):
        self.gate.decide(self.request.id, "pratham", True)
        self.assertFalse(self.gate.is_approved(self.request.id, "create_jenkins_job", "other-job"))

    def test_approval_does_not_transfer_to_other_tool(self):
        self.gate.decide(self.request.id, "pratham", True)
        self.assertFalse(self.gate.is_approved(self.request.id, "trigger_jenkins_build", "web-ci"))

    def test_rejected_request_is_not_approved(self):
        self.gate.decide(self.request.id, "pratham", False)
        self.assertFalse(self.gate.is_approved(self.request.id, "create_jenkins_job", "web-ci"))

    def test_decision_cannot_be_changed_twice(self):
        self.gate.decide(self.request.id, "pratham", False)
        with self.assertRaises(ValueError):
            self.gate.decide(self.request.id, "pratham", True)

    def test_unknown_approval_id_is_not_approved(self):
        self.assertFalse(self.gate.is_approved("missing", "create_jenkins_job", "web-ci"))


if __name__ == "__main__":
    unittest.main()
