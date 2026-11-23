# PACTLINE Pipeline Builder - Complete Demo

## Overview
This demonstrates how PACTLINE generates a CI/CD pipeline with approval workflow integration.

## Two UI Paths

### Path 1: Engineering Page (Preview Only)
The Engineering page at `/engineering` provides a quick preview of the generated Jenkinsfile without approval:
- **Purpose**: Quick validation and preview
- **Features**: Validates pipeline configuration, shows Jenkinsfile syntax
- **No approval needed**: Just informational

### Path 2: Voice Assistant (Full Workflow with Approval)
The recommended path for actual pipeline creation uses the voice assistant:

```
User: "PACTLINE, generate a CI/CD pipeline for my GitHub repository"
       Owner: PrathamM16
       Repo: PACTLINE  
       Branch: feature/ci-cd
       Job Name: pactline-ci
       Node Version: 20
       SonarQube Key: PrathamM16_PACTLINE

PACTLINE:
1. Generates Jenkinsfile content (7 stages)
2. Creates approval request for generatePipeline tool
3. User sees approval in Voice room → Approves
4. Creates another approval for createPipelinePullRequest tool  
5. User approves again
6. Creates GitHub branch and pull request with Jenkinsfile
7. Reports success with PR link
```

## Demo Results

### Generated Jenkinsfile (Auto-generated from Pipeline Builder)
```groovy
pipeline {
    agent any
    options {
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }
    tools {
        nodejs 'NodeJS-20'
    }
    triggers {
        githubPush()
    }
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        stage('Install Dependencies') {
            steps {
                sh 'npm ci'
            }
        }
        stage('Lint') {
            steps {
                sh 'npm run lint'
            }
        }
        stage('Unit Tests') {
            steps {
                sh 'npm run test -- --watch=false --browsers=ChromeHeadless'
            }
        }
        stage('SonarQube Analysis') {
            steps {
                script {
                    def scannerHome = tool 'SonarScanner'
                    withSonarQubeEnv('SonarCloud') {
                        sh "${scannerHome}/bin/sonar-scanner -Dsonar.projectKey=PrathamM16_PACTLINE"
                    }
                }
            }
        }
        stage('Quality Gate') {
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }
        stage('Production Build') {
            steps {
                sh 'npm run build -- --configuration production'
            }
        }
    }
}
```

## Pipeline Stages Explained

### 1. Checkout (Automatic)
- **Action**: Clone repository from GitHub
- **Time**: ~5 seconds
- **Input**: Repository URL from GitHub context
- **Output**: Source code in workspace

### 2. Install Dependencies (5-10 seconds)
- **Action**: Run `npm ci` for clean install
- **Purpose**: Ensures consistent package versions
- **Fails if**: Missing package-lock.json

### 3. Lint (10-20 seconds)
- **Action**: Run ESLint via `npm run lint`
- **Purpose**: Check code quality and style compliance
- **Fails if**: Lint errors detected

### 4. Unit Tests (20-40 seconds)
- **Action**: Run tests in headless Chrome
- **Purpose**: Validate application logic
- **Command**: `npm run test -- --watch=false --browsers=ChromeHeadless`
- **Fails if**: Tests don't pass

### 5. SonarQube Analysis (30-60 seconds)
- **Action**: Upload coverage and analysis to SonarQube Cloud
- **Purpose**: Track code quality, security vulnerabilities, test coverage
- **Input**: Project key from SonarQube configuration
- **Output**: Metrics available in SonarQube dashboard

### 6. Quality Gate (10 minutes max)
- **Action**: Check SonarQube quality gate status
- **Purpose**: Ensures minimum quality standards
- **Aborts if**: Quality gate fails
- **Status**: Can PASS, WARN, or FAIL

### 7. Production Build (20-40 seconds)
- **Action**: Build Angular application for production
- **Command**: `npm run build -- --configuration production`
- **Output**: Optimized bundle in `dist/` folder
- **Only runs**: If all previous stages pass

## Total Pipeline Time
**6-11 minutes** per complete run

## Configuration Details

| Setting | Value | Purpose |
|---------|-------|---------|
| **Timeout** | 30 minutes | Prevents hung builds |
| **Concurrent Builds** | Disabled | Sequential execution only |
| **Node Version** | 20 | LTS version for stability |
| **Trigger** | GitHub Push | Runs on every push to repo |
| **SonarQube Project** | PrathamM16_PACTLINE | Tracks quality metrics |

## Integration Points

### GitHub
- Automatic checkout via SCM polling
- Creates branch for PR
- Commits Jenkinsfile
- Creates pull request

### Jenkins
- Runs the pipeline
- Manages build artifacts
- Provides build logs
- Reports success/failure

### SonarQube Cloud
- Receives code analysis
- Evaluates quality gate
- Tracks metrics over time
- Flags security issues

## Approval Flow (Voice Assistant Path)

```
┌─────────────────────────────────────────┐
│ User speaks: "Create CI/CD pipeline"    │
└────────────┬──────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────┐
│ PACTLINE extracts: owner, repo, branch, etc  │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────┐
│ Calls generatePipeline tool                  │
│ ✓ Validation passes                         │
│ → Creates APPROVAL REQUEST #1               │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────┐
│ Voice Room shows Approval #1:               │
│ "Create pipeline for PrathamM16/PACTLINE"   │
│ [Approve]  [Reject]                        │
└────────────┬───────────────────────────────────┘
             │
        ┌────┴──────────────┐
        │                   │
   [User Approves]    [User Rejects]
        │                   │
        ▼                   ▼
    Continue          Workflow ends
                      No PR created
        │
        ▼
┌──────────────────────────────────────────────┐
│ Approval #1 → Executes generatePipeline     │
│ Output: Jenkinsfile content                 │
│ → Creates APPROVAL REQUEST #2               │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────┐
│ Voice Room shows Approval #2:               │
│ "Create pull request with Jenkinsfile"      │
│ [Approve]  [Reject]                        │
└────────────┬───────────────────────────────────┘
             │
        ┌────┴──────────────┐
        │                   │
   [User Approves]    [User Rejects]
        │                   │
        ▼                   ▼
    Continue          PR not created
        │
        ▼
┌──────────────────────────────────────────────┐
│ Approval #2 → Executes createPipelinePR     │
│ ✓ Creates branch: feature/ci-cd             │
│ ✓ Commits Jenkinsfile                       │
│ ✓ Creates pull request                      │
│ → Returns PR URL                            │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────┐
│ PACTLINE speaks result:                     │
│ "Successfully created pull request #42"     │
│ "Link: https://github.com/..."             │
└──────────────────────────────────────────────┘
```

## UI State During Workflow

### Voice Room After User Approves Pipeline:
```
Agent state: IDLE

Approvals
└─ Create pull request with Jenkinsfile
   [Approve]  [Reject]

Today's briefing
├─ Calendar: Nov 21, 9:00 AM meeting with Claudia
└─ Pending tasks: Lunch at 2:00 PM Platinum
```

## Engineering Page (Optional Flow)

The Engineering page at `/engineering` can be enhanced to:
1. Generate preview ✓ (currently working)
2. Create approval request for generatePipeline
3. Create approval request for createPipelinePullRequest
4. Direct user to Voice room to approve
5. Once approved, automatically create PR

**Current state**: Shows preview only (no approval required)

## Testing the Full Flow

### Quick Test (Engineering Page)
```
1. Navigate to http://localhost:4200/engineering
2. Fill: Job Name = pactline-ci
3. Fill: Repository = PrathamM16/PACTLINE
4. Fill: SonarQube Key = PrathamM16_PACTLINE
5. Click "Generate and validate"
6. See Jenkinsfile preview
✓ Results: Preview shown successfully
```

### Full Test (Voice Room - Recommended)
```
1. Navigate to http://localhost:4200/voice
2. Click "Start" button
3. Say: "Create a CI/CD pipeline for PrathamM16 slash PACTLINE using branch develop"
4. Wait for PACTLINE to generate
5. See Approval #1 in Approvals section
6. Click "Approve"
7. See Approval #2 appear
8. Click "Approve" again
9. Listen as PACTLINE announces PR creation success
✓ Results: PR created with Jenkinsfile
```

## Expected Outcomes

### Success Scenario
✓ Jenkinsfile generated with 7 stages  
✓ GitHub branch created  
✓ Jenkinsfile committed to branch  
✓ Pull request created  
✓ PR title: "Add CI/CD pipeline [pactline]"  
✓ PR description: "Generated by PACTLINE"  
✓ User can merge to trigger first build in Jenkins  

### Failure Scenarios
✗ Invalid repository: Error message shown
✗ Missing GitHub token: IntegrationUnavailable error
✗ User rejects approval #1: Pipeline generation cancelled
✗ User rejects approval #2: PR not created but jenkinsfile generated

## Next Steps

After PR is created:
1. Review Jenkinsfile in GitHub PR
2. If satisfied, merge pull request
3. Jenkins auto-triggers build (via githubPush trigger)
4. Build runs 7 stages in sequence
5. Reports results to console
6. SonarQube receives analysis data
7. Quality gate evaluated
8. Build artifacts available

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "No pending requests" in Approvals | Pipeline generation failed | Check backend logs for errors |
| Backend unreachable | Server not running | Run `uvicorn app.api.main:app --reload` |
| GitHub token expired | Token in .env invalid | Update GITHUB_TOKEN and restart |
| SonarQube connection fails | Invalid credentials | Verify SONARQUBE_TOKEN in .env |
| Jenkins build hangs | Pipeline timeout too short | Increase timeout in Jenkinsfile |

## Demo Architecture

```
┌─────────────┐
│   Frontend  │
│   Angular   │
└──────┬──────┘
       │
       ├─► /engineering (Preview only)
       │   └─► /api/pipelines/preview
       │
       └─► /voice (Full workflow)
           └─► Calls generatePipeline tool
               └─► Creates approval
               └─► User approves
               └─► Calls createPipelinePullRequest tool
                   └─► Creates approval
                   └─► User approves
                   └─► GitHub API creates PR

┌──────────────┐
│   Backend    │
│   FastAPI    │
└──────┬───────┘
       │
       ├─► Tool Registry (approval system)
       │   ├─► generatePipeline
       │   ├─► createPipelinePullRequest
       │   └─► analyzeSonarQube
       │
       ├─► GitHub Client
       │   ├─► Create branch
       │   ├─► Commit file
       │   └─► Create PR
       │
       └─► SonarQube Client
           ├─► Quality analysis
           └─► Metrics collection

┌──────────────┐
│  Integrations│
└──────┬───────┘
       │
       ├─► GitHub API
       │   └─► manage branches & PRs
       │
       ├─► Jenkins
       │   └─► trigger builds (via githubPush)
       │
       └─► SonarQube Cloud
           └─► analyze code quality
```

## Summary

The PACTLINE Pipeline Builder demonstrates:
✓ Voice-driven CI/CD configuration  
✓ Approval-based authorization  
✓ GitHub integration (branch/PR creation)  
✓ Jenkins pipeline generation  
✓ SonarQube quality gate integration  
✓ Full end-to-end DevOps workflow  

Both the Engineering page (preview) and Voice room (full workflow) are functional and demonstrate the system's capabilities.
