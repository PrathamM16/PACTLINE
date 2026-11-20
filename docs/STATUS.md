# Status (iteration 3, 2026-11-20)

See docs/TEST_REPORT.md for what was executed and docs/FAQ_CHECK.md for hackathon requirements.

## Added in iteration 3
- Authentication (scrypt passwords, HS256 tokens), workspace membership and roles, rate limiting
- Per-session signed tool tokens; identity derived on the server, never from the browser or the LLM
- Server-held approvals: write tools only create a pending approval; only an authenticated user can approve
- Persistent storage with versioned migrations (SQLite locally, PostgreSQL via psycopg; Postgres path not yet run)
- Idempotency scoped per workspace; webhook replay protection stored in the database
- Frontend synced: login, approvals panel, authenticated API calls

## Deviation from earlier plan
SQLAlchemy/Alembic were replaced by a small migration runner (app/storage.py) so the persistence layer could be tested here.

## Added in iteration 4 (FAQ gaps)
- Google Calendar: list events, clash detection before approval, create event with deterministic id (duplicate-safe), refresh-token auth, one-time authorization script
- Email reminders with background scheduler, retry cap, honest pending/sent/failed status
- Briefing now includes real calendar, shopping lists and follow-ups; Outcome panel in the UI; demo-context seed; judge-ready demo script
- Agent prompt: clash handling, no early 'sent' claims, language mirroring

## Still missing
Live verification of everything above, voice-driven DevOps, multi-person rooms, connection pooling, dashboards beyond Voice/Approvals/Integrations/Pipeline.

---
# Earlier status
# Honest status (second iteration)

## Verified by execution in the build sandbox (152 unit tests, all passing)
- Everything from iteration 1 (commitment ledger, approval gate, workflow engine, webhook HMAC, Jenkinsfile generation/validation, Jenkins and Sonar clients)
- Tool registry: server-side confirmation gate, idempotency by tool_call_id, workspace isolation, date validation, audit events
- Agora join-payload builder: structure checked against the documented schema (see list below), tool specs obey Agora's documented limits and the template-placeholder rules

## Verified against current official docs (read this session), NOT executed against live services
- Start agent: POST https://api.agora.io/api/conversational-ai-agent/v2/projects/{appid}/join, stop: .../agents/{agent_id}/leave (Main docs, updated 2026-09-27)
- Murf TTS in Main docs: vendor "murf", params api_key, base_url wss://global.api.murf.ai/v1/speech/stream-input, voiceId, locale, rate, pitch, model "FALCON", sample_rate
- Live transcripts need advanced_features.enable_rtm=true and parameters.data_channel="rtm", plus Agora RTM and the Web toolkit
- Custom tools: llm.tools[] with function/execution/server, advanced_features.enable_tools=true, HTTPS only, complete-placeholder rule, headers cannot use {{args}}
- Token generation with agora-token-builder (RTC and RTM) and agora-rtm-sdk usage, per the "Build a backend and client" page

## Still unverified
- Exact npm export names of agora-agent-client-toolkit (see SETUP.md section 5)
- REST Basic-auth page was not opened; I used base64(customerId:customerSecret), the standard form the SDK page also describes
- Whether remote_rtc_uids supports several users (REST page says one; SDK example uses "*"). The code subscribes to the single user's uid, so multi-person rooms are NOT done
- Murf Falcon access on your plan, and that Agora accepts your Murf key: only a live run can show this
- Everything in the Angular app (never built), FastAPI runtime (never started)

## Not built yet
- Google Calendar OAuth and events; reminder delivery (reminders are stored with delivery "not_sent")
- PostgreSQL repositories (the tool registry and ledger are in memory: data is lost on restart), Alembic migrations
- Authentication and RBAC (workspace/user ids come from the client in this build: NOT secure for production)
- LLM-driven Engineering workspace by voice (DevOps tools exist as backend code but are not exposed as Agora tools yet)
- WebSocket events, dashboards, approval/audit/memory screens, notifications, e2e tests
- Deployment and cloud Jenkins/SonarQube setup
