import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.accounts import Accounts
from app.devops.pipeline import PipelineSpec, generate_jenkinsfile, validate_jenkinsfile, validate_spec
from app.domain.tools import ToolContext, ToolRegistry
from app.domain.webhooks import verify_signature
from app.integrations import agora
from app.integrations.gcal import GoogleCalendar
from app.integrations.http import urllib_transport
from app.integrations.mailer import SmtpMailer
from app.security import RateLimiter
from app.service import AppService, ServiceError
from app.storage import open_store

load_dotenv()
log = logging.getLogger("pactline")

REMINDER_POLL_SECONDS = 30


async def _reminder_loop():
    while True:
        await asyncio.sleep(REMINDER_POLL_SECONDS)
        try:
            await asyncio.get_running_loop().run_in_executor(None, get_service().deliver_reminders)
        except HTTPException:
            continue
        except Exception:
            log.exception("reminder delivery cycle failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_reminder_loop())
    yield
    task.cancel()


app = FastAPI(title="PACTLINE API", version="0.4.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Workspace-Id"],
)

AUTH_LIMIT = RateLimiter(10, 60)
USER_LIMIT = RateLimiter(120, 60)
TOOL_LIMIT = RateLimiter(240, 60)
_service: AppService | None = None

SERVICE_KEYS = {
    "agora": ["AGORA_APP_ID", "AGORA_APP_CERTIFICATE", "AGORA_CUSTOMER_ID", "AGORA_CUSTOMER_SECRET"],
    "murf": ["MURF_API_KEY"],
    "llm": ["LLM_API_KEY", "LLM_MODEL"],
    "google_calendar": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"],
    "email_reminders": ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"],
    "github": ["GITHUB_TOKEN"],
    "jenkins": ["JENKINS_BASE_URL", "JENKINS_USERNAME", "JENKINS_API_TOKEN"],
    "sonarqube": ["SONARQUBE_CLOUD_URL", "SONARQUBE_TOKEN"],
}


def get_service() -> AppService:
    global _service
    if _service is None:
        secret = os.environ.get("JWT_SECRET", "")
        if len(secret) < 32:
            raise HTTPException(status_code=503, detail="server misconfigured: JWT_SECRET must be at least 32 characters")
        store = open_store(os.environ.get("DATABASE_URL") or "sqlite:///pactline.db")
        tz_name = os.environ.get("USER_TIMEZONE", "Asia/Kolkata")
        calendar = GoogleCalendar.from_env(os.environ, urllib_transport)
        mailer = SmtpMailer.from_env(os.environ)
        registry = ToolRegistry(store, calendar=calendar, timezone=tz_name, mail_configured=mailer is not None)
        _service = AppService(store, Accounts(store.db), registry, secret, agora, os.environ.get("PUBLIC_API_URL", ""), mailer=mailer, tz_name=tz_name)
    return _service


@app.exception_handler(ServiceError)
async def service_error_handler(_: Request, error: ServiceError):
    return JSONResponse(status_code=error.status, content={"detail": error.detail})


@app.exception_handler(agora.AgoraNotConfigured)
async def agora_not_configured_handler(_: Request, error: agora.AgoraNotConfigured):
    return JSONResponse(status_code=503, content={"detail": f"voice unavailable: {error}"})


@app.exception_handler(agora.AgoraRequestError)
async def agora_request_error_handler(_: Request, error: agora.AgoraRequestError):
    log.error("agora request failed: %s", error)
    return JSONResponse(status_code=502, content={"detail": "voice provider request failed"})


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def current_user(authorization: str | None = Header(default=None)) -> str:
    user_id = get_service().authenticate(authorization)
    if not USER_LIMIT.allow(user_id):
        raise HTTPException(status_code=429, detail="too many requests")
    return user_id


def workspace(user_id: str = Depends(current_user), x_workspace_id: str | None = Header(default=None)) -> ToolContext:
    return get_service().context(user_id, x_workspace_id)


class RegisterRequest(BaseModel):
    email: str = Field(max_length=254)
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class VoiceTokenRequest(BaseModel):
    user_uid: int = Field(gt=0, lt=2_000_000_000)


class VoiceStartRequest(BaseModel):
    channel: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class VoiceStopRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=128)


class DecisionRequest(BaseModel):
    approve: bool


class PipelineRequest(BaseModel):
    job_name: str
    repository: str
    branch: str
    app_type: str = "angular"
    node_version: str
    stages: list[str]
    sonar_project_key: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/ready")
def ready():
    try:
        get_service().store.db.query("SELECT 1 AS ok")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ready"}


@app.post("/api/auth/register")
def register(body: RegisterRequest, request: Request):
    if os.environ.get("ALLOW_REGISTRATION", "true").lower() != "true":
        raise HTTPException(status_code=403, detail="registration is closed")
    if not AUTH_LIMIT.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail="too many requests")
    return get_service().register(body.email, body.name, body.password)


@app.post("/api/auth/login")
def login(body: LoginRequest, request: Request):
    if not AUTH_LIMIT.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail="too many requests")
    return get_service().login(body.email, body.password)


@app.get("/api/me")
def me(user_id: str = Depends(current_user)):
    return {"user_id": user_id, "workspaces": get_service().accounts.workspaces_for(user_id)}


@app.get("/api/integrations/status")
def integration_status(_: ToolContext = Depends(workspace)):
    return {name: {"configured": all(os.environ.get(k) for k in keys), "verified_live": False} for name, keys in SERVICE_KEYS.items()}


@app.post("/api/pipelines/preview")
def preview_pipeline(body: PipelineRequest, _: ToolContext = Depends(workspace)):
    spec = PipelineSpec(body.job_name, body.repository, body.branch, body.app_type, body.node_version, tuple(body.stages), body.sonar_project_key)
    errors = validate_spec(spec)
    if errors:
        return {"valid": False, "errors": errors}
    content = generate_jenkinsfile(spec)
    problems = validate_jenkinsfile(content)
    return {"valid": not problems, "errors": problems, "jenkinsfile": content, "approval_required": True}


@app.post("/api/voice/token")
def voice_token(body: VoiceTokenRequest, ctx: ToolContext = Depends(workspace)):
    return get_service().voice_token(ctx, body.user_uid)


@app.post("/api/voice/start")
def voice_start(body: VoiceStartRequest, ctx: ToolContext = Depends(workspace)):
    return get_service().voice_start(ctx, body.channel)


@app.post("/api/voice/stop")
def voice_stop(body: VoiceStopRequest, ctx: ToolContext = Depends(workspace)):
    return get_service().voice_stop(ctx, body.agent_id)


@app.post("/tools/{tool_name}")
async def run_tool(tool_name: str, request: Request, authorization: str | None = Header(default=None)):
    if not TOOL_LIMIT.allow("tools"):
        raise HTTPException(status_code=429, detail="too many requests")
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid json")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="body must be an object")
    return get_service().tool_call(authorization, tool_name, body)


@app.get("/api/approvals")
def list_approvals(ctx: ToolContext = Depends(workspace)):
    return get_service().pending_approvals(ctx)


@app.post("/api/approvals/{approval_id}/decide")
def decide_approval(approval_id: str, body: DecisionRequest, ctx: ToolContext = Depends(workspace)):
    return get_service().decide(ctx, approval_id, body.approve)


def _read_tool(ctx: ToolContext, name: str, args: dict):
    return get_service().registry.call(name, ctx, args)["data"]


@app.get("/api/briefing")
def briefing(ctx: ToolContext = Depends(workspace)):
    return _read_tool(ctx, "getDailyBriefing", {"unused": ""})


@app.get("/api/tasks")
def tasks(ctx: ToolContext = Depends(workspace)):
    return _read_tool(ctx, "listTasks", {"assignee": ""})


@app.get("/api/commitments")
def commitments(ctx: ToolContext = Depends(workspace)):
    return _read_tool(ctx, "listCommitments", {"owner": ""})


@app.post("/api/demo/seed")
def seed_demo(ctx: ToolContext = Depends(workspace)):
    return get_service().seed_demo(ctx)


@app.post("/api/reminders/run")
def run_reminders(ctx: ToolContext = Depends(workspace)):
    return get_service().run_reminders(ctx)


@app.get("/api/audit")
def audit(ctx: ToolContext = Depends(workspace)):
    return get_service().audit(ctx)


@app.post("/webhooks/github")
async def github_webhook(request: Request, x_hub_signature_256: str | None = Header(default=None), x_github_delivery: str | None = Header(default=None), x_github_event: str | None = Header(default=None)):
    raw = await request.body()
    if not verify_signature(os.environ.get("GITHUB_WEBHOOK_SECRET", ""), raw, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="invalid signature")
    if not x_github_delivery:
        raise HTTPException(status_code=400, detail="missing delivery id")
    store = get_service().store
    if not store.once(f"webhook:{x_github_delivery}"):
        return {"status": "duplicate"}
    payload = json.loads(raw)
    store.put("webhook", "system", x_github_delivery, {"delivery": x_github_delivery, "event": x_github_event, "repository": payload.get("repository", {}).get("full_name")})
    store.audit("system", "github", "webhook_received", str(x_github_event), "accepted")
    return {"status": "accepted"}
