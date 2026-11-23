# PACTLINE Quick Start - Voice DevOps Assistant

## ✅ Completed Setup

Your PACTLINE instance is now fully configured with:

- ✅ **Agora Voice** - Real-time audio communication
- ✅ **Groq LLM** - Natural language understanding (Llama 2 model)
- ✅ **Murf Voice Synthesis** - Text-to-speech responses
- ✅ **Google Calendar** - Event scheduling and timezone support
- ✅ **GitHub Integration** - Repository access and pull request creation
- ✅ **Jenkins** - CI/CD pipeline execution
- ✅ **SQLite Database** - Persistent session storage
- ✅ **DevOps Voice Tools** - 3 new tools for GitHub + pipeline workflows

## 🚀 To Run the Application

### Terminal 1: Start Backend
```bash
cd D:\PACTLINE\backend
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --port 8000
```

### Terminal 2: Start Frontend
```bash
cd D:\PACTLINE\frontend
npm start
```

### Visit in Browser
```
http://localhost:4200
```

## 📝 Login Credentials

**Test Account** (pre-seeded):
- Email: `qa-tester@example.com`
- Password: `QaTester-12345`

## 🎤 Voice Commands to Try

After logging in and clicking "Voice":

### 1. List Repositories
> "List my repositories"
>
> Agent will read your GitHub repos

### 2. Generate a Pipeline
> "Create a CI/CD pipeline for PrathamM16/PACTLINE on feature/ci-cd with Node 20"
>
> Agent will:
> - Generate a Jenkinsfile
> - Request your approval
> - Wait for you to click "Approve"

### 3. Create Pull Request
After approval, agent will:
- Create a feature branch
- Commit the Jenkinsfile
- Open a pull request on GitHub
- Tell you the PR URL

### 4. Analyze Code Quality
> "Analyze the code quality of PrathamM16_PACTLINE"
>
> Agent will:
> - Query SonarQube
> - Report bugs, vulnerabilities, coverage
> - Recommend whether code is production-ready

## 🔍 Verification Checklist

### Backend Status
```powershell
curl.exe http://localhost:8000/health
```
Expected: `{"status":"ok"}`

### Frontend Running
```powershell
curl.exe http://localhost:4200
```
Expected: Redirects to login

### Integrations Status
After login: Visit http://localhost:4200/integrations
- ✅ GitHub: "configured"
- ✅ Jenkins: "configured"
- ✅ Google Calendar: "configured"
- ✅ Murf: "configured"
- ✅ Agora: "configured"

## 📊 What Each Voice Tool Does

| Tool | Use Case | Requires Approval |
|------|----------|-------------------|
| `listRepositories` | See all your GitHub repos | No |
| `generatePipeline` | Create a Jenkinsfile | Yes |
| `createPipelinePullRequest` | Open PR with Jenkinsfile | Yes |

## 🗂️ Key Files Changed This Session

### Backend
- **app/integrations/github.py** - GitHub API client (NEW)
- **app/domain/tools.py** - Added 3 DevOps voice tool handlers
- **app/api/main.py** - Checks for GitHub token in SERVICE_KEYS
- **.env** - Added GITHUB_TOKEN and Jenkins credentials

### Frontend
- **src/app/voice/convo-session.ts** - Fixed Agora RTM constructor

### Configuration
- **.env** - All credentials loaded (see DEVOPS_VOICE_GUIDE.md)

## 🐛 If Something Breaks

### Restart Backend
```bash
# Kill old processes
Get-Process python | Stop-Process -Force

# Restart
cd D:\PACTLINE\backend
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --port 8000
```

### Clear Database (Fresh Start)
```bash
rm D:\PACTLINE\backend\pactline.db
# Then restart backend to recreate schema
```

### Check Logs
```bash
# Backend logs appear in terminal
# Look for errors about: GitHub, Jenkins, Groq, Agora

# Frontend logs: Browser DevTools (F12 → Console)
```

## 📞 Next Steps

1. **Try the demo flow**: List repos → Generate pipeline → Approve → Create PR
2. **Check the GitHub PR**: Visit your repo to see the new Jenkinsfile PR
3. **Trigger the build**: Merge PR in GitHub to run the pipeline on Jenkins
4. **Explore other features**: Calendar integration, task management

## 🎯 Demo Scenario

**Say this to PACTLINE:**

> "Connect to my GitHub repository PrathamM16/PACTLINE. Create a CI/CD pipeline for my Angular application. Run tests, perform SonarQube analysis, and tell me whether the build is production-ready."

**Expected Result:**
1. ✅ Agent lists your repos (voice response)
2. ✅ Agent generates a Jenkinsfile with stages:
   - Install dependencies
   - Lint
   - Unit tests
   - SonarQube analysis
   - Quality gate check
   - Build artifact
3. ✅ Approval popup appears in UI
4. ✅ You click "Approve"
5. ✅ Agent creates a feature branch
6. ✅ Agent commits Jenkinsfile
7. ✅ Agent opens a pull request
8. ✅ Agent tells you the PR URL

## 📖 Full Documentation

See **DEVOPS_VOICE_GUIDE.md** for:
- Complete architecture overview
- All environment variables
- Troubleshooting guide
- API reference
- Project structure

---

**Status**: ✅ Ready for Demo  
**Version**: 0.4.0  
**Last Tested**: November 2026
