# SonarQube Integration Guide

## Overview

PACTLINE now includes **SonarQube Cloud integration** for automated code quality analysis. This allows voice commands to:
- Analyze code quality metrics
- Check security vulnerabilities
- Verify quality gates before deployment
- Get AI-powered recommendations for fixes

## Configuration

### Environment Variables

Add these to `.env`:

```env
SONARQUBE_CLOUD_URL=https://sonarcloud.io
SONARQUBE_TOKEN=<your-sonarqube-token>
SONARQUBE_PROJECT_KEY=<your-project-key>
SONARQUBE_ORGANIZATION=<your-org>
```

### Example Configuration

**For PACTLINE Project**:
```env
SONARQUBE_CLOUD_URL=https://sonarcloud.io
SONARQUBE_TOKEN=f874a6b10cbc39f8bbd3ec2ef1d2ec60028417c0
SONARQUBE_PROJECT_KEY=PrathamM16_PACTLINE
SONARQUBE_ORGANIZATION=prathamm16
```

## Getting Credentials

### 1. Create SonarQube Cloud Account
- Visit https://sonarcloud.io
- Sign up with GitHub account
- Create organization (or use existing)

### 2. Create Project
- Navigate to Projects → Create Project
- Select repository from GitHub
- SonarQube auto-detects and sets up analysis
- Note the project key (shown in project settings)

### 3. Generate API Token
- Go to User → My Account → Security
- Create token: "PACTLINE DevOps" (or preferred name)
- Copy token immediately (can't retrieve later)

### 4. Configure in .env
```bash
SONARQUBE_TOKEN=<token-from-step-3>
SONARQUBE_PROJECT_KEY=<project-key>
```

## Voice Commands

### Analyze Code Quality

**Command**: "Analyze the code quality of PrathamM16_PACTLINE"

**Response**: 
```
Your PACTLINE project analysis shows:
- Quality Gate: UNCLEAR
- Coverage: 0% (not yet configured)
- Bugs: 1 issue found
- Vulnerabilities: 7 security issues detected
- Code Smells: 1 maintainability issue

Recommendation: Quality gate status is unclear. Review SonarQube dashboard 
for details before deployment.
```

### Check Quality Before Deployment

**Command**: "Is PrathamM16_PACTLINE production-ready?"

**Response** (if gate passes):
```
✓ Quality gate PASSED
✓ Coverage meets threshold
✓ No critical vulnerabilities
✓ All code quality metrics pass

This build is production-ready. Ready to merge and deploy.
```

**Response** (if gate fails):
```
✗ Quality gate FAILED
✗ Code coverage is below threshold
✗ Security vulnerabilities detected

Address issues before deployment:
1. Increase test coverage to 80%
2. Fix 7 security vulnerabilities
3. Resolve maintainability issues
```

## Metrics Analyzed

| Metric | Description | Threshold |
|--------|-------------|-----------|
| **Coverage** | % of code covered by tests | 80% (configurable) |
| **Line Coverage** | % of executable lines covered | - |
| **Bugs** | Potential bugs detected | 0 (quality gate fails if > 0) |
| **Vulnerabilities** | Security issues found | 0 (quality gate fails if > 0) |
| **Code Smells** | Maintainability issues | Configurable |
| **Complexity** | Cyclomatic complexity | 10 per file (avg) |
| **Duplicated Lines** | % of duplicated code | < 3% (recommended) |
| **Tests** | Number of tests | Per project |
| **Test Success** | % of tests passing | 100% |

## Quality Gate Conditions

Default SonarQube quality gate checks:

1. **Coverage** (new code): ≥ 80%
2. **Duplicated Lines**: < 3%
3. **Maintainability Rating**: A
4. **Security Rating**: A
5. **Reliability Rating**: A
6. **Security Hotspots**: 100% reviewed

## Integration with CI/CD Pipeline

### Generate Pipeline with SonarQube

**Voice Command**:
> "Create a CI/CD pipeline for PrathamM16/PACTLINE with SonarQube analysis"

**Generated Jenkinsfile** includes:

```groovy
stage('SonarQube Analysis') {
    steps {
        script {
            sh 'npm run sonar'
        }
    }
}

stage('Quality Gate Check') {
    steps {
        waitForQualityGate abortPipeline: true
    }
}
```

**Flow**:
1. Code is built and tested
2. SonarQube analyzer runs
3. Code is uploaded to SonarQube Cloud
4. Quality gate is evaluated
5. Pipeline stops if gate fails (can't deploy bad code)
6. Pipeline continues if gate passes

## SonarQube API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `/api/qualitygates/project_status` | Get quality gate pass/fail status |
| `/api/measures/component` | Get metrics (coverage, bugs, etc.) |
| `/api/issues/search` | Get open issues and violations |

## Approval Workflow with SonarQube

When creating a pipeline:

```
User: "Create pipeline for PrathamM16_PACTLINE with SonarQube"
  ↓
Agent: Generates Jenkinsfile with Sonar stage
  ↓
UI: Shows approval card with pipeline content
  ↓
User: Clicks "Approve"
  ↓
Agent: Creates PR on GitHub
  ↓
PR created with Jenkinsfile containing SonarQube analysis
  ↓
User: Merges PR in GitHub
  ↓
Jenkins triggers build
  ↓
Build runs → Tests → SonarQube scan → Quality gate check
  ↓
If quality gate PASSES: Deployment proceeds
If quality gate FAILS: Pipeline stops, blocks deployment
```

## Common Issues & Solutions

### "Project not found" Error
**Cause**: Project key is incorrect or project is private
**Solution**: 
- Get exact key from SonarQube dashboard (Project → Key)
- Ensure project visibility is set to Public (or token has access)

### "Token invalid or expired"
**Cause**: Token was revoked or expired
**Solution**:
- Generate new token at SonarQube: User → My Account → Security
- Update `.env` with new token
- Restart backend

### Zero Coverage Reported
**Cause**: Coverage report not generated by build
**Solution**:
- Ensure test runner generates coverage report
- For Angular: `ng test --code-coverage`
- For Node.js: `jest --coverage`
- Sonar configuration includes coverage path

### Quality Gate Stuck
**Cause**: Gate conditions not properly configured
**Solution**:
- Visit SonarQube project → Quality Gates → Edit
- Ensure conditions are set correctly
- Re-analyze project after changes

## Setup Coverage Reporting

### For Angular Projects

**1. Update `karma.conf.js`**:
```javascript
coverageReporter: {
  dir: require('path').join(__dirname, './coverage'),
  subdir: '.',
  reporters: [
    { type: 'html' },
    { type: 'text-summary' },
    { type: 'lcovonly' },  // Required for SonarQube
  ]
}
```

**2. Update `sonar-project.properties`**:
```properties
sonar.projectKey=PrathamM16_PACTLINE
sonar.projectName=PACTLINE
sonar.sources=src
sonar.exclusions=**/*.spec.ts
sonar.tests=src
sonar.test.inclusions=**/*.spec.ts
sonar.javascript.lcov.reportPaths=coverage/lcov.info
```

**3. Run with coverage**:
```bash
ng test --code-coverage --watch=false
sonar-scanner
```

## SonarQube Dashboard

Access your project dashboard:
```
https://sonarcloud.io/dashboard?id=<project-key>
```

**Key sections**:
- **Overview**: Overall health, main metrics
- **Code**: Source code with issue highlighting
- **Issues**: All bugs, vulnerabilities, code smells
- **Measures**: Detailed metrics and trends
- **Activity**: History of analysis runs
- **Quality Gate**: Current gate status and conditions

## Webhook Integration (Future)

PACTLINE can receive SonarQube webhook notifications:

**Webhook URL** (once deployed):
```
https://your-pactline-instance.com/webhooks/sonarqube
```

**Webhook Events**:
- Quality gate status changes
- New issues detected
- Coverage changes

**Setup** (in SonarQube):
1. Administration → Webhooks
2. Create webhook
3. URL: `https://your-pactline.com/webhooks/sonarqube`
4. Events: Quality gate

## Best Practices

1. **Set Realistic Quality Gates**: Don't aim for 100% coverage, but >80%
2. **Fix Issues Early**: Address issues as they're found, not after PR
3. **Code Review**: Combine SonarQube with peer code review
4. **Monitor Trends**: Check quality metrics over time
5. **Automate**: Let CI/CD pipeline enforce quality gates
6. **Educate Team**: Share reports and discuss improvements
7. **Customize**: Adjust rules and thresholds for your project

## SonarQube Rule Customization

Adjust what SonarQube considers an issue:

**In SonarQube Dashboard**:
1. Administration → Quality Profiles
2. Find "Sonar way" or project profile
3. Click "Rules" tab
4. Enable/disable rules as needed
5. Save and re-analyze

**Common customizations**:
- Disable overly strict naming rules
- Adjust complexity thresholds
- Exclude generated files from analysis
- Customize security rules for your stack

## Resources

- **SonarCloud**: https://sonarcloud.io
- **SonarQube Docs**: https://docs.sonarqube.org
- **SonarQube API**: https://sonarcloud.io/web_api
- **Quality Profiles**: https://docs.sonarqube.org/latest/instance-administration/quality-profiles/

---

**Version**: 0.4.0  
**Integration Type**: Read-only Quality Analysis  
**Status**: ✅ Configured and Working
