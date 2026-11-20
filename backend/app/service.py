import secrets
from datetime import date, datetime, timedelta, timezone

from app.accounts import Accounts
from app.domain.tools import ToolContext, ToolRegistry
from app.reminders import deliver_due
from app.security import AuthError, issue_token, verify_token
from app.storage import Store

ACCESS_TTL = 8 * 3600
TOOL_TTL = 3600


class ServiceError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


class AppService:
    def __init__(self, store: Store, accounts: Accounts, registry: ToolRegistry, secret: str, agora, public_url: str, mailer=None, tz_name: str = "Asia/Kolkata", today=date.today):
        self.store = store
        self.accounts = accounts
        self.registry = registry
        self._secret = secret
        self._agora = agora
        self._public_url = public_url
        self._mailer = mailer
        self._tz = tz_name
        self._today = today

    def register(self, email: str, name: str, password: str) -> dict:
        try:
            ids = self.accounts.register(email, name, password)
        except ValueError as exc:
            raise ServiceError(400, str(exc))
        return self.login(email, password) | {"workspace_id": ids["workspace_id"]}

    def login(self, email: str, password: str) -> dict:
        user = self.accounts.authenticate(email, password)
        if user is None:
            raise ServiceError(401, "invalid credentials")
        token = issue_token(self._secret, {"typ": "access", "sub": user["id"]}, ACCESS_TTL)
        return {"access_token": token, "user": user, "workspaces": self.accounts.workspaces_for(user["id"])}

    def authenticate(self, bearer: str | None) -> str:
        if not bearer or not bearer.startswith("Bearer "):
            raise ServiceError(401, "authentication required")
        try:
            return verify_token(self._secret, bearer[7:], "access")["sub"]
        except AuthError:
            raise ServiceError(401, "invalid or expired token")

    def context(self, user_id: str, workspace_id: str | None) -> ToolContext:
        role = self.accounts.role(user_id, workspace_id) if workspace_id else None
        if role is None:
            raise ServiceError(403, "not a member of this workspace")
        return ToolContext(workspace_id, user_id, role, self.accounts.profile(user_id)["email"])

    def voice_token(self, ctx: ToolContext, user_uid: int) -> dict:
        if ctx.role not in ("owner", "member"):
            raise ServiceError(403, "this role cannot start voice sessions")
        if user_uid == self._agora.AGENT_UID or user_uid <= 0:
            raise ServiceError(400, "invalid uid")
        channel = "pactline-" + secrets.token_hex(8)
        tokens = self._agora.build_tokens(channel, user_uid)
        self.store.put("voice_session", ctx.workspace_id, channel, {"channel": channel, "user_id": ctx.user_id, "user_uid": user_uid, "status": "issued", "agent_id": None})
        self.store.audit(ctx.workspace_id, ctx.user_id, "voice_token", channel, "issued")
        return {"channel": channel, "agentUid": self._agora.AGENT_UID, **tokens}

    def voice_start(self, ctx: ToolContext, channel: str) -> dict:
        if not self._public_url.startswith("https://"):
            raise ServiceError(503, "PUBLIC_API_URL must be an https URL reachable by Agora")
        session = self.store.get("voice_session", ctx.workspace_id, channel)
        if session is None or session["user_id"] != ctx.user_id:
            raise ServiceError(403, "unknown voice session")
        if session["status"] != "issued" or not self.store.once(f"voice:{channel}"):
            raise ServiceError(409, "voice session already started")
        tool_token = issue_token(self._secret, {"typ": "tool", "sub": ctx.user_id, "ws": ctx.workspace_id, "ch": channel}, TOOL_TTL)
        try:
            settings = self._agora.load_settings()
            agent_token = self._agora.build_tokens(channel, self._agora.AGENT_UID)["rtcToken"]
            specs = self._agora.tool_specs(self._public_url, self.registry.definitions())
            payload = self._agora.build_join_payload(channel, agent_token, session["user_uid"], tool_token, specs, settings)
            result = self._agora.start_agent(payload)
        except Exception as exc:
            self.store.put("voice_session", ctx.workspace_id, channel, {**session, "status": "failed"})
            self.store.audit(ctx.workspace_id, ctx.user_id, "voice_start", channel, "failed", str(exc))
            raise
        self.store.put("voice_session", ctx.workspace_id, channel, {**session, "status": "active", "agent_id": result.get("agent_id")})
        self.store.audit(ctx.workspace_id, ctx.user_id, "voice_start", channel, "started")
        return {"agentId": result.get("agent_id"), "status": result.get("status")}

    def voice_stop(self, ctx: ToolContext, agent_id: str) -> dict:
        sessions = [s for s in self.store.list_records("voice_session", ctx.workspace_id) if s["agent_id"] == agent_id]
        if not sessions or (sessions[0]["user_id"] != ctx.user_id and ctx.role != "owner"):
            raise ServiceError(403, "unknown voice session")
        self._agora.stop_agent(agent_id)
        self.store.put("voice_session", ctx.workspace_id, sessions[0]["channel"], {**sessions[0], "status": "stopped"})
        self.store.audit(ctx.workspace_id, ctx.user_id, "voice_stop", sessions[0]["channel"], "stopped")
        return {"stopped": True}

    def tool_call(self, bearer: str | None, tool_name: str, body: dict) -> dict:
        if not bearer or not bearer.startswith("Bearer "):
            raise ServiceError(401, "unauthorized")
        try:
            claims = verify_token(self._secret, bearer[7:], "tool")
        except AuthError:
            raise ServiceError(401, "unauthorized")
        session = self.store.get("voice_session", claims["ws"], claims["ch"])
        if session is None or session["status"] != "active" or session["user_id"] != claims["sub"]:
            raise ServiceError(401, "voice session is not active")
        role = self.accounts.role(claims["sub"], claims["ws"])
        if role is None:
            raise ServiceError(403, "membership revoked")
        arguments = dict(body)
        call_id = str(arguments.pop("tool_call_id", ""))
        return self.registry.call(tool_name, ToolContext(claims["ws"], claims["sub"], role, self.accounts.profile(claims["sub"])["email"]), arguments, call_id)

    def pending_approvals(self, ctx: ToolContext) -> list[dict]:
        return self.registry.pending_approvals(ctx)

    def decide(self, ctx: ToolContext, approval_id: str, approve: bool) -> dict:
        try:
            return self.registry.decide(ctx, approval_id, approve)
        except KeyError:
            raise ServiceError(404, "unknown approval")
        except PermissionError as exc:
            raise ServiceError(403, str(exc))
        except ValueError as exc:
            raise ServiceError(409, str(exc))

    def audit(self, ctx: ToolContext) -> list[dict]:
        if ctx.role != "owner":
            raise ServiceError(403, "owners only")
        return self.store.audit_list(ctx.workspace_id)

    def deliver_reminders(self) -> dict:
        return deliver_due(self.store, self._mailer, datetime.now(timezone.utc), self._tz)

    def run_reminders(self, ctx: ToolContext) -> dict:
        if ctx.role != "owner":
            raise ServiceError(403, "owners only")
        if self._mailer is None:
            raise ServiceError(503, "email delivery is not configured (SMTP_HOST, SMTP_USER, SMTP_PASSWORD)")
        return self.deliver_reminders()

    def seed_demo(self, ctx: ToolContext) -> dict:
        if ctx.role != "owner":
            raise ServiceError(403, "owners only")
        if not self.store.once(f"seed:{ctx.workspace_id}"):
            raise ServiceError(409, "demo context already loaded")
        name = self.accounts.profile(ctx.user_id)["name"]
        today = self._today()
        self.store.put("preference", ctx.workspace_id, f"{ctx.workspace_id}:meetings", {"key": "meetings", "value": "I prefer meetings after 10 AM"})
        task = {"id": secrets.token_hex(8), "title": "Visit the bank", "assignee": name, "due_date": (today + timedelta(days=1)).isoformat(), "status": "pending", "created_by": ctx.user_id}
        self.store.put("task", ctx.workspace_id, task["id"], task)
        self.registry.ledger.propose(name, "submit the project report", today + timedelta(days=2), "demo", ctx.workspace_id, "Loaded demo context", ctx.user_id)
        self.store.audit(ctx.workspace_id, ctx.user_id, "seed_demo", ctx.workspace_id, "loaded")
        return {"loaded": ["preference", "task", "commitment"]}
