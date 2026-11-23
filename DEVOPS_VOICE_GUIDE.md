# PACTLINE DevOps Voice Assistant - Implementation Guide

## Overview

PACTLINE is a voice-driven DevOps assistant that helps developers manage CI/CD pipelines, GitHub operations, and approvals through natural language commands. It combines:

- **Agora RTM** (Audio/messaging) for real-time voice communication
- **Groq LLM** (Llama 2) for natural language understanding
- **Murf Falcon** for voice synthesis (text-to-speech)
- **Google Calendar** integration for scheduling
- **GitHub API** for repository management
- **Jenkins** for pipeline execution
- **SonarQube** for code quality analysis

## Architecture

### Backend Stack
- **Framework**: FastAPI (Python)
- **Database**: SQLite (persistent session storage)
- **Authentication**: JWT tokens with separate scopes (access, tool, voice)
- **Tool Registry**: Voice tools are registered with approval workflows

### Frontend Stack
- **Framework**: Angular 18 (TypeScript)
- **Voice UI**: Real-time transcript, approvals, briefing dashboard
- **Components**:
  - Login/Registration
  - Voice Room (main interaction)
  - Engineering (pipeline builder preview)
  - Integrations status page

## Configuration

### Environment Variables (.env)

Required for core functionality:
```
# JWT
JWT_SECRET=<32+ character secret>

# Database
DATABASE_URL=sqlite:///pactline.db

# Timezone
USER_TIMEZONE=Asia/Kolkata

# LLM (Groq)
LLM_API_KEY=<groq-api-key>
LLM_MODEL=mixtral-8x7b-32768  # or llama-2-70b-chat
LLM_URL=https://api.groq.com/openai/v1/chat/completions

# Agora (Voice)
AGORA_APP_ID=<app-id>
AGORA_APP_CERTIFICATE=<certificate>
AGORA_CUSTOMER_ID=<customer-id>
AGORA_CUSTOMER_SECRET=<customer-secret>

# Murf (Voice Synthesis)
MURF_API_KEY=<murf-api-key>
MURF_MODEL=Falcon  # Falcon or Nova
MURF_LOCALE=en-US

# Google Calendar
GOOGLE_CLIENT_ID=<oauth-client-id>
GOOGLE_CLIENT_SECRET=<oauth-client-secret>
GOOGLE_REFRESH_TOKEN=<refresh-token>

# GitHub
GITHUB_TOKEN=<personal-access-token>

# Jenkins
JENKINS_BASE_URL=http://localhost:8080/
JENKINS_USERNAME=admin
JENKINS_API_TOKEN=<api-token>

# CORS
CORS_ORIGINS=http://localhost:4200,http://localhost:8000

# Optional
ALLOW_REGISTRATION=true
PUBLIC_API_URL=http://localhost:8000
```

## Voice Tools

### 1. `listRepositories`
Lists all GitHub repositories accessible to the user.

**Usage**: "List my repositories" or "Show my repos"

**Returns**: Repository list with URLs and descriptions

**Example Response**:
```json
{
  "status": "success",
  "data": {
    "repos": [
      {
        "id": 123456,
        "name": "PACTLINE",
        "full_name": "PrathamM16/PACTLINE",
        "url": "https://github.com/PrathamM16/PACTLINE",
        "description": "Voice-driven DevOps assistant",
        "default_branch": "main"
      }
    ]
  }
}
```

### 2. `generatePipeline` ⚠️ Needs Approval
Generates a Jenkinsfile for a specified repository.

**Usage**: "Generate a CI/CD pipeline for PrathamM16/PACTLINE on develop with Node 20"

**Parameters**:
- `owner`: GitHub owner (e.g., "PrathamM16")
- `repo`: Repository name (e.g., "PACTLINE")
- `branch`: Target branch (e.g., "feature/ci-cd")
- `job_name`: Jenkins job name
- `node_version`: Node.js version
- `sonar_key`: SonarQube project key (optional)

**Returns**: Jenkinsfile content and approval request

**Approval Flow**:
1. Agent generates pipeline content
2. User sees approval card in Voice Room
3. User clicks "Approve" to proceed
4. System moves to next step (PR creation)

### 3. `createPipelinePullRequest` ⚠️ Needs Approval
Creates a GitHub pull request with the generated Jenkinsfile.

**Usage**: "Create a PR for the pipeline"

**Parameters**:
- `owner`: GitHub owner
- `repo`: Repository name
- `branch`: Feature branch name
- `title`: PR title
- `base_branch`: Target branch (default: "main")
- `jenkinsfile`: Jenkinsfile content

**Returns**: PR URL and number

**Example Response**:
```json
{
  "status": "success",
  "data": {
    "ok": true,
    "pr_url": "https://github.com/PrathamM16/PACTLINE/pull/42",
    "pr_number": 42
  }
}
```

### 4. `analyzeSonarQube` (NEW)
Analyzes code quality and security using SonarQube Cloud.

**Usage**: "Analyze the code quality of PrathamM16_PACTLINE" or "Is PrathamM16_PACTLINE production-ready?"

**Parameters**:
- `project_key`: SonarQube project key (e.g., "PrathamM16_PACTLINE")

**Returns**: Quality metrics and gate status

**Example Response**:
```json
{
  "status": "success",
  "data": {
    "project_key": "PrathamM16_PACTLINE",
    "quality_gate_passed": false,
    "quality_gate_status": "NONE",
    "coverage": 0.0,
    "bugs": 1,
    "vulnerabilities": 7,
    "code_smells": 1,
    "open_issues": 9,
    "recommendation": "Quality gate status is unclear. Review SonarQube dashboard for details.",
    "failed_conditions": []
  }
}
```

## Voice Room UI

### Status Badges
- **IDLE**: Agent is idle, ready for voice input
- **LISTENING**: Microphone is active, capturing speech
- **SPEAKING**: Agent is responding with voice
- **ERROR**: Something went wrong
- **DISCONNECTED**: Voice session not active

### Live Transcript
Shows real-time speech recognition as you speak.

### Approvals Card
When a tool needs approval:
1. Shows the pending action (e.g., "Create Jenkinsfile: pactline-ci")
2. Displays summary of changes
3. "Approve" button to confirm
4. "Reject" button to cancel

### Briefing Dashboard
Shows:
- **Calendar**: Today and tomorrow's events
- **Pending Tasks**: Tasks due today
- **Reminders**: Sent/failed/pending notifications
- **Commitments**: Team commitments

## End-to-End Demo Flow

### Scenario: "Create CI/CD pipeline for my Angular project"

**User Voice Input**: "List my repositories"
1. Frontend: `Start` button activates microphone
2. Agora RTM: Sends audio to voice provider
3. Backend: LLM processes intent → identifies tool `listRepositories`
4. Tool: Calls GitHub API, returns repos
5. Murf: Synthesizes response ("I found 42 repositories...")
6. UI: Updates briefing with repo list

**User Voice Input**: "Create a pipeline for PACTLINE on feature/ci-cd with Node 20"
1. LLM identifies tool `generatePipeline`
2. Tool: Generates Jenkinsfile with stages
   - Install dependencies
   - Run linter
   - Unit tests
   - SonarQube analysis
   - Quality gate check
   - Build artifact
3. Backend: Creates approval request
4. UI: Shows approval card "Generate Jenkinsfile: pactline-ci"
5. User: Clicks "Approve"
6. Tool: Creates feature branch on GitHub
7. Tool: Commits Jenkinsfile to branch
8. Tool: Opens pull request
9. Murf: "I've created a pull request at https://..."

**Result**: PR is ready for review and merge to trigger the pipeline

## Testing

### Quick Test: Verify All Integrations
```bash
cd frontend
npm start
# In another terminal:
cd backend
python -m uvicorn app.api.main:app --reload --port 8000
```

### Visit Application
- Login: http://localhost:4200/
- Voice Room: Click "Voice" in nav after login
- Integrations: Click "Integrations" to see configuration status

### Manual Tool Testing (requires active voice session)
1. Go to Voice Room
2. Click "Start"
3. Allow microphone
4. Speak: "List my repositories"
5. Listen for voice response
6. See transcript and briefing update

## Project Structure

```
PACTLINE/
├── backend/
│   ├── app/
│   │   ├── api/main.py           # FastAPI routes
│   │   ├── service.py            # Business logic
│   │   ├── domain/
│   │   │   ├── tools.py          # Tool registry + handlers
│   │   │   └── webhooks.py       # GitHub webhook verification
│   │   ├── integrations/
│   │   │   ├── agora.py          # Agora RTM client
│   │   │   ├── github.py         # GitHub API client
│   │   │   ├── gcal.py           # Google Calendar client
│   │   │   ├── jenkins.py        # Jenkins client
│   │   │   └── http.py           # HTTP utilities
│   │   ├── devops/
│   │   │   └── pipeline.py       # Jenkinsfile generator
│   │   ├── security.py           # JWT tokens, rate limiting
│   │   └── storage.py            # SQLite persistence
│   └── .env                       # Environment config
├── frontend/
│   ├── src/app/
│   │   ├── voice/
│   │   │   ├── voice-room.component.ts
│   │   │   └── convo-session.ts  # Agora RTM client
│   │   ├── engineering/
│   │   │   └── engineering.component.ts
│   │   ├── core/
│   │   │   ├── auth.ts           # Login/logout
│   │   │   ├── briefing.component.ts
│   │   │   └── integrations.component.ts
│   │   └── styles.css            # Global styles
│   └── angular.json
└── scripts/
    └── google_auth.py            # OAuth callback handler
```

## Common Issues & Troubleshooting

### "RTMClient is not a constructor"
**Solution**: Agora RTM SDK v2 exports changed. Use `new AgoraRTM.RTM(...)` not `new RTMClient()`.
- File: `frontend/src/app/voice/convo-session.ts`

### "Voice provider request failed"
**Causes**:
1. `LLM_URL` is empty in `.env`
2. `LLM_API_KEY` is invalid
3. Agora credentials are incorrect

**Solution**: 
```bash
# Check .env has these set:
LLM_URL=https://api.groq.com/openai/v1/chat/completions
LLM_API_KEY=<your-groq-api-key>
```

### Calendar events showing in wrong timezone
**Solution**: Backend converts Google Calendar UTC times to `USER_TIMEZONE`.
- Default: `Asia/Kolkata`
- Change in `.env`: `USER_TIMEZONE=America/New_York`

### "Not a member of this workspace"
**Causes**: 
1. Session cleared (database reset)
2. User removed from workspace
3. Token expired

**Solution**: Auto-logout and redirect to login on 403 errors.

### GitHub token doesn't work
**Check**:
1. Token has scope: `repo` (full control)
2. Token hasn't expired
3. User is not blocked on GitHub

**Generate new token**: https://github.com/settings/personal-access-tokens/new

### Jenkins connection fails
**Check**:
1. Jenkins is running: `http://localhost:8080`
2. API token is valid (not password)
3. Username is correct (usually "admin")
4. Network connectivity if running in Docker

## Future Enhancements

1. **Pipeline Triggering**: "Trigger the PACTLINE pipeline"
2. **Build Status**: "What's the status of the latest build?"
3. **SonarQube Integration**: Quality gate checks in approval
4. **Multi-repo Pipelines**: Support for monorepos
5. **Custom Stages**: User-defined build stages
6. **Webhook Triggers**: Auto-create pipelines on PR events
7. **Deployment Approvals**: Gate production deployments
8. **Notifications**: Slack/Teams alerts for build results

## Support & Debugging

Enable detailed logging:
```python
# backend/app/api/main.py
logging.basicConfig(level=logging.DEBUG)
```

Check database state:
```bash
sqlite3 pactline.db
sqlite> .tables
sqlite> SELECT * FROM voice_session;
sqlite> SELECT * FROM approval;
```

## API Reference

### Authentication
All endpoints except `/health`, `/health/ready`, `/api/auth/*`, and `/webhooks/*` require:
```
Authorization: Bearer <access_token>
X-Workspace-Id: <workspace_id>
```

### Voice Session Lifecycle
1. `POST /api/voice/token` → Get token for audio stream
2. `POST /api/voice/start` → Start voice session, get agent ID
3. `Agora RTM` → Real-time transcription + tool calls
4. `POST /api/voice/stop` → End session

### Tool Invocation
Tools are called via `/tools/{tool_name}` during active voice sessions with a tool token (issued during voice start).

### Approvals
- `GET /api/approvals` → List pending approvals
- `POST /api/approvals/{id}/decide` → Approve/reject

---

**Version**: 0.4.0  
**Last Updated**: November 2026  
**Author**: PACTLINE Development Team
