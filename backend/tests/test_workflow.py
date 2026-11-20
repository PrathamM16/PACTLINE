import unittest

from app.domain.workflow import InvalidTransition, Step, WAIT, Workflow, WorkflowState


def noop():
    return "done"


def explode():
    raise RuntimeError("provider down")


def make_workflow(steps):
    return Workflow("u1", "w1", "c1", "intent", steps)


class FlakyHandler:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls < 2:
            raise RuntimeError("transient")
        return "recovered"


class WorkflowTest(unittest.TestCase):
    def test_medium_risk_workflow_requires_approval(self):
        workflow = make_workflow([Step("task", "create_task", noop)])
        workflow.submit()
        self.assertEqual(workflow.state, WorkflowState.READY_FOR_APPROVAL)

    def test_low_risk_workflow_skips_approval(self):
        workflow = make_workflow([Step("read", "retrieve_commitments", noop)])
        workflow.submit()
        self.assertEqual(workflow.state, WorkflowState.APPROVED)

    def test_unapproved_workflow_cannot_run(self):
        workflow = make_workflow([Step("task", "create_task", noop)])
        workflow.submit()
        with self.assertRaises(InvalidTransition):
            workflow.run()

    def test_approved_workflow_completes(self):
        workflow = make_workflow([Step("task", "create_task", noop)])
        workflow.submit()
        workflow.approve()
        self.assertEqual(workflow.run(), WorkflowState.COMPLETED)

    def test_failure_without_progress_is_failed(self):
        workflow = make_workflow([Step("job", "create_jenkins_job", explode)])
        workflow.submit()
        workflow.approve()
        self.assertEqual(workflow.run(), WorkflowState.FAILED)

    def test_failure_after_progress_is_partially_completed(self):
        workflow = make_workflow([Step("task", "create_task", noop), Step("job", "create_jenkins_job", explode)])
        workflow.submit()
        workflow.approve()
        self.assertEqual(workflow.run(), WorkflowState.PARTIALLY_COMPLETED)

    def test_failed_step_records_error_message(self):
        step = Step("job", "create_jenkins_job", explode)
        workflow = make_workflow([step])
        workflow.submit()
        workflow.approve()
        workflow.run()
        self.assertEqual(step.error, "provider down")

    def test_retry_policy_recovers_from_transient_error(self):
        step = Step("task", "create_task", FlakyHandler(), max_attempts=3)
        workflow = make_workflow([step])
        workflow.submit()
        workflow.approve()
        self.assertEqual(workflow.run(), WorkflowState.COMPLETED)

    def test_waiting_step_pauses_workflow(self):
        workflow = make_workflow([Step("build", "trigger_jenkins_build", lambda: WAIT)])
        workflow.submit()
        workflow.approve()
        self.assertEqual(workflow.run(), WorkflowState.WAITING_FOR_EXTERNAL_EVENT)

    def test_external_event_resumes_workflow(self):
        workflow = make_workflow([Step("build", "trigger_jenkins_build", lambda: WAIT)])
        workflow.submit()
        workflow.approve()
        workflow.run()
        self.assertEqual(workflow.resume("build", "SUCCESS"), WorkflowState.COMPLETED)

    def test_resume_requires_waiting_state(self):
        workflow = make_workflow([Step("task", "create_task", noop)])
        with self.assertRaises(InvalidTransition):
            workflow.resume("task", "x")

    def test_cancelled_workflow_is_terminal(self):
        workflow = make_workflow([Step("task", "create_task", noop)])
        workflow.cancel()
        with self.assertRaises(InvalidTransition):
            workflow.approve()

    def test_completed_step_is_not_repeated_after_resume(self):
        counter = []
        steps = [Step("task", "create_task", lambda: counter.append(1) or "ok"), Step("build", "trigger_jenkins_build", lambda: WAIT)]
        workflow = make_workflow(steps)
        workflow.submit()
        workflow.approve()
        workflow.run()
        workflow.resume("build", "SUCCESS")
        self.assertEqual(len(counter), 1)


if __name__ == "__main__":
    unittest.main()
