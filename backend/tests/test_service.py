import unittest
from types import SimpleNamespace

from app.accounts import Accounts
from app.domain.tools import ToolRegistry
from app.integrations import agora as real_agora
from app.security import issue_token
from app.service import AppService, ServiceError
from app.storage import open_store

SECRET = "service-test-secret"


class FakeAgora:
    AGENT_UID = real_agora.AGENT_UID

    def __init__(self):
        self.started = []
        self.stopped = []
        self.fail_start = False

    def build_tokens(self, channel, uid):
        return {"rtcToken": f"rtc-{uid}", "rtmToken": f"rtm-{uid}", "expireAt": 1, "appId": "app"}

    def load_settings(self):
        return {"llm_url": "u", "llm_api_key": "k", "llm_model": "m", "murf_api_key": "mk", "murf_voice_id": "Matthew", "murf_locale": "en-US", "murf_model": "FALCON", "asr_language": "en-US"}

    tool_specs = staticmethod(real_agora.tool_specs)
    build_join_payload = staticmethod(real_agora.build_join_payload)

    def start_agent(self, payload):
        if self.fail_start:
            raise RuntimeError("agora down")
        self.started.append(payload)
        return {"agent_id": "agent-1", "status": "RUNNING"}

    def stop_agent(self, agent_id):
        self.stopped.append(agent_id)
        return {}


def build():
    store = open_store("sqlite:///:memory:")
    fake = FakeAgora()
    service = AppService(store, Accounts(store.db), ToolRegistry(store), SECRET, fake, "https://api.example.com")
    return service, fake


def signup(service, email="a@example.com"):
    service.register(email, "Asha", "long-enough-pass")
    login = service.login(email, "long-enough-pass")
    return login["user"]["id"], login["workspaces"][0]["id"], login["access_token"]


def started_session(service):
    user_id, workspace_id, _ = signup(service)
    ctx = service.context(user_id, workspace_id)
    token = service.voice_token(ctx, 4242)
    service.voice_start(ctx, token["channel"])
    return ctx, token["channel"]


def tool_bearer(service, ctx, channel):
    return "Bearer " + issue_token(SECRET, {"typ": "tool", "sub": ctx.user_id, "ws": ctx.workspace_id, "ch": channel}, 60)


class AuthenticationTest(unittest.TestCase):
    def test_login_returns_access_token(self):
        service, _ = build()
        self.assertIn("access_token", service.register("a@example.com", "Asha", "long-enough-pass"))

    def test_bad_password_is_unauthorized(self):
        service, _ = build()
        service.register("a@example.com", "Asha", "long-enough-pass")
        with self.assertRaises(ServiceError) as raised:
            service.login("a@example.com", "wrong-password-1")
        self.assertEqual(raised.exception.status, 401)

    def test_missing_bearer_is_unauthorized(self):
        with self.assertRaises(ServiceError) as raised:
            build()[0].authenticate(None)
        self.assertEqual(raised.exception.status, 401)

    def test_valid_bearer_returns_user_id(self):
        service, _ = build()
        user_id, _, token = signup(service)
        self.assertEqual(service.authenticate("Bearer " + token), user_id)

    def test_tool_token_is_not_accepted_as_access_token(self):
        service, _ = build()
        forged = "Bearer " + issue_token(SECRET, {"typ": "tool", "sub": "x"}, 60)
        with self.assertRaises(ServiceError):
            service.authenticate(forged)

    def test_non_member_cannot_get_workspace_context(self):
        service, _ = build()
        _, workspace_id, _ = signup(service)
        intruder, _, _ = signup(service, "b@example.com")
        with self.assertRaises(ServiceError) as raised:
            service.context(intruder, workspace_id)
        self.assertEqual(raised.exception.status, 403)

    def test_missing_workspace_header_is_forbidden(self):
        service, _ = build()
        user_id, _, _ = signup(service)
        with self.assertRaises(ServiceError):
            service.context(user_id, None)


class VoiceSessionTest(unittest.TestCase):
    def setUp(self):
        self.service, self.fake = build()
        user_id, workspace_id, _ = signup(self.service)
        self.ctx = self.service.context(user_id, workspace_id)

    def test_voice_token_binds_channel_to_user(self):
        token = self.service.voice_token(self.ctx, 4242)
        self.assertEqual(self.service.store.get("voice_session", self.ctx.workspace_id, token["channel"])["user_id"], self.ctx.user_id)

    def test_agent_uid_cannot_be_used_as_user_uid(self):
        with self.assertRaises(ServiceError):
            self.service.voice_token(self.ctx, self.fake.AGENT_UID)

    def test_viewer_cannot_request_voice_token(self):
        viewer_ctx = self.ctx.__class__(self.ctx.workspace_id, self.ctx.user_id, "viewer")
        with self.assertRaises(ServiceError):
            self.service.voice_token(viewer_ctx, 4242)

    def test_start_rejects_channel_not_issued_to_user(self):
        with self.assertRaises(ServiceError) as raised:
            self.service.voice_start(self.ctx, "pactline-made-up")
        self.assertEqual(raised.exception.status, 403)

    def test_start_rejects_channel_issued_to_other_user(self):
        token = self.service.voice_token(self.ctx, 4242)
        other_id, _, _ = signup(self.service, "b@example.com")
        self.service.accounts.add_member(self.ctx.workspace_id, other_id, "member")
        with self.assertRaises(ServiceError):
            self.service.voice_start(self.service.context(other_id, self.ctx.workspace_id), token["channel"])

    def test_start_returns_agent_id(self):
        token = self.service.voice_token(self.ctx, 4242)
        self.assertEqual(self.service.voice_start(self.ctx, token["channel"])["agentId"], "agent-1")

    def test_second_start_for_same_channel_conflicts(self):
        token = self.service.voice_token(self.ctx, 4242)
        self.service.voice_start(self.ctx, token["channel"])
        with self.assertRaises(ServiceError) as raised:
            self.service.voice_start(self.ctx, token["channel"])
        self.assertEqual(raised.exception.status, 409)

    def test_start_sends_session_token_not_identity_to_agora(self):
        token = self.service.voice_token(self.ctx, 4242)
        self.service.voice_start(self.ctx, token["channel"])
        variables = self.fake.started[0]["properties"]["llm"]["template_variables"]
        self.assertTrue(variables["tool_auth"].startswith("Bearer ey"))

    def test_failed_start_marks_session_failed(self):
        token = self.service.voice_token(self.ctx, 4242)
        self.fake.fail_start = True
        with self.assertRaises(RuntimeError):
            self.service.voice_start(self.ctx, token["channel"])
        self.assertEqual(self.service.store.get("voice_session", self.ctx.workspace_id, token["channel"])["status"], "failed")

    def test_stop_calls_agora_for_own_session(self):
        token = self.service.voice_token(self.ctx, 4242)
        self.service.voice_start(self.ctx, token["channel"])
        self.service.voice_stop(self.ctx, "agent-1")
        self.assertEqual(self.fake.stopped, ["agent-1"])

    def test_stop_rejects_unknown_agent(self):
        with self.assertRaises(ServiceError):
            self.service.voice_stop(self.ctx, "agent-of-someone-else")

    def test_stop_from_other_workspace_never_reaches_agora(self):
        token = self.service.voice_token(self.ctx, 4242)
        self.service.voice_start(self.ctx, token["channel"])
        other_id, other_ws, _ = signup(self.service, "b@example.com")
        with self.assertRaises(ServiceError):
            self.service.voice_stop(self.service.context(other_id, other_ws), "agent-1")
        self.assertEqual(self.fake.stopped, [])


class ToolEndpointTest(unittest.TestCase):
    def setUp(self):
        self.service, _ = build()
        self.ctx, self.channel = started_session(self.service)
        self.bearer = tool_bearer(self.service, self.ctx, self.channel)
        self.args = {"title": "Book hotel", "assignee": "", "due_date": ""}

    def test_missing_authorization_is_rejected(self):
        with self.assertRaises(ServiceError) as raised:
            self.service.tool_call(None, "createTask", self.args)
        self.assertEqual(raised.exception.status, 401)

    def test_access_token_is_not_accepted_on_tool_endpoint(self):
        access = "Bearer " + issue_token(SECRET, {"typ": "access", "sub": self.ctx.user_id}, 60)
        with self.assertRaises(ServiceError):
            self.service.tool_call(access, "createTask", self.args)

    def test_identity_comes_from_token_not_body(self):
        body = {**self.args, "workspace_id": "someone-elses", "user_id": "admin", "tool_call_id": "c1"}
        result = self.service.tool_call(self.bearer, "createTask", body)
        self.assertEqual(self.service.registry.pending_approvals(self.ctx)[0]["requested_by"], self.ctx.user_id)
        self.assertEqual(result["status"], "awaiting_user_approval")

    def test_valid_call_creates_pending_approval_in_token_workspace(self):
        self.service.tool_call(self.bearer, "createTask", self.args)
        self.assertEqual(len(self.service.pending_approvals(self.ctx)), 1)

    def test_call_after_stop_is_rejected(self):
        self.service.voice_stop(self.ctx, "agent-1")
        with self.assertRaises(ServiceError):
            self.service.tool_call(self.bearer, "createTask", self.args)

    def test_call_for_unstarted_channel_is_rejected(self):
        issued = self.service.voice_token(self.ctx, 5555)
        with self.assertRaises(ServiceError):
            self.service.tool_call(tool_bearer(self.service, self.ctx, issued["channel"]), "createTask", self.args)

    def test_revoked_membership_blocks_tool_calls(self):
        self.service.accounts._db.execute("DELETE FROM memberships WHERE user_id = ?", (self.ctx.user_id,))
        with self.assertRaises(ServiceError) as raised:
            self.service.tool_call(self.bearer, "createTask", self.args)
        self.assertEqual(raised.exception.status, 403)

    def test_duplicate_tool_call_id_creates_one_approval(self):
        body = {**self.args, "tool_call_id": "dup"}
        self.service.tool_call(self.bearer, "createTask", body)
        self.service.tool_call(self.bearer, "createTask", body)
        self.assertEqual(len(self.service.pending_approvals(self.ctx)), 1)

    def test_unknown_tool_reports_error_without_exception(self):
        self.assertEqual(self.service.tool_call(self.bearer, "formatDisk", {})["error"], "unknown_tool")

    def test_forged_tool_token_is_rejected(self):
        forged = "Bearer " + issue_token("attacker-secret", {"typ": "tool", "sub": self.ctx.user_id, "ws": self.ctx.workspace_id, "ch": self.channel}, 60)
        with self.assertRaises(ServiceError):
            self.service.tool_call(forged, "createTask", self.args)


class ApprovalEndpointTest(unittest.TestCase):
    def setUp(self):
        self.service, _ = build()
        self.ctx, self.channel = started_session(self.service)
        bearer = tool_bearer(self.service, self.ctx, self.channel)
        self.approval_id = self.service.tool_call(bearer, "createTask", {"title": "x", "assignee": "", "due_date": ""})["approval_id"]

    def test_authenticated_owner_can_approve(self):
        self.assertEqual(self.service.decide(self.ctx, self.approval_id, True)["status"], "executed")

    def test_unknown_approval_is_not_found(self):
        with self.assertRaises(ServiceError) as raised:
            self.service.decide(self.ctx, "missing", True)
        self.assertEqual(raised.exception.status, 404)

    def test_second_decision_conflicts(self):
        self.service.decide(self.ctx, self.approval_id, True)
        with self.assertRaises(ServiceError) as raised:
            self.service.decide(self.ctx, self.approval_id, True)
        self.assertEqual(raised.exception.status, 409)

    def test_member_cannot_decide_owners_approval(self):
        member_id, _, _ = signup(self.service, "m@example.com")
        self.service.accounts.add_member(self.ctx.workspace_id, member_id, "member")
        with self.assertRaises(ServiceError) as raised:
            self.service.decide(self.service.context(member_id, self.ctx.workspace_id), self.approval_id, True)
        self.assertEqual(raised.exception.status, 403)

    def test_audit_log_is_owner_only(self):
        viewer = self.ctx.__class__(self.ctx.workspace_id, self.ctx.user_id, "viewer")
        with self.assertRaises(ServiceError):
            self.service.audit(viewer)

    def test_owner_can_read_audit_log(self):
        self.assertGreater(len(self.service.audit(self.ctx)), 0)


if __name__ == "__main__":
    unittest.main()


class PublicUrlTest(unittest.TestCase):
    def test_start_requires_https_public_url(self):
        service, _ = build()
        service._public_url = "http://localhost:8000"
        user_id, workspace_id, _ = signup(service)
        ctx = service.context(user_id, workspace_id)
        channel = service.voice_token(ctx, 4242)["channel"]
        with self.assertRaises(ServiceError) as raised:
            service.voice_start(ctx, channel)
        self.assertEqual(raised.exception.status, 503)


class DemoSeedAndRemindersTest(unittest.TestCase):
    def setUp(self):
        self.service, _ = build()
        user_id, workspace_id, _ = signup(self.service)
        self.ctx = self.service.context(user_id, workspace_id)

    def test_seed_loads_preference_task_and_commitment(self):
        self.assertEqual(self.service.seed_demo(self.ctx)["loaded"], ["preference", "task", "commitment"])

    def test_seed_makes_briefing_contain_stored_preference(self):
        self.service.seed_demo(self.ctx)
        briefing = self.service.registry.call("getDailyBriefing", self.ctx, {"unused": ""})["data"]
        self.assertEqual(briefing["preferences"]["meetings"], "I prefer meetings after 10 AM")

    def test_seed_makes_briefing_contain_pending_commitment(self):
        self.service.seed_demo(self.ctx)
        briefing = self.service.registry.call("getDailyBriefing", self.ctx, {"unused": ""})["data"]
        self.assertEqual(len(briefing["pending_commitments"]), 1)

    def test_seed_twice_conflicts(self):
        self.service.seed_demo(self.ctx)
        with self.assertRaises(ServiceError) as raised:
            self.service.seed_demo(self.ctx)
        self.assertEqual(raised.exception.status, 409)

    def test_seed_is_owner_only(self):
        member = self.ctx.__class__(self.ctx.workspace_id, self.ctx.user_id, "member")
        with self.assertRaises(ServiceError):
            self.service.seed_demo(member)

    def test_manual_reminder_run_without_mailer_reports_unavailable(self):
        with self.assertRaises(ServiceError) as raised:
            self.service.run_reminders(self.ctx)
        self.assertEqual(raised.exception.status, 503)

    def test_context_carries_account_email_for_reminders(self):
        self.assertEqual(self.ctx.email, "a@example.com")
