# Pipeline Builder - Form Fields Guide

## Overview
The Pipeline Builder creates a CI/CD pipeline (Jenkinsfile) for your project. Here's what to enter in each field:

---

## Form Fields Explained

### 1. **Job Name**
**What it is**: The name of your Jenkins job/pipeline

**Example values**:
- `pactline-ci`
- `angular-app-pipeline`
- `my-project-build`

**Rules**:
- Use lowercase letters and hyphens
- No spaces
- 1-50 characters
- Example: `pactline-ci-angular`

---

### 2. **Repository** ⭐ Important
**What it is**: Your GitHub repository in format `owner/repo`

**Example values**:
- `PrathamM16/PACTLINE` (for PACTLINE project)
- `PrathamM16/angular-learning-app`
- `your-username/your-repo-name`

**How to find it**:
1. Go to your GitHub repository
2. Copy the URL: `https://github.com/YOUR_USERNAME/REPO_NAME`
3. Format: `YOUR_USERNAME/REPO_NAME`

**For PACTLINE**: `PrathamM16/PACTLINE`

---

### 3. **Branch**
**What it is**: The Git branch where the Jenkinsfile will be created

**Example values**:
- `feature/ci-cd` (creates a new feature branch)
- `develop` (commits to existing branch)
- `feature/pipeline-setup`
- `ci-cd-automation`

**Rules**:
- Use lowercase and hyphens
- Branch will be created if it doesn't exist
- Best practice: Use feature branches like `feature/something`

**For PACTLINE**: `feature/ci-cd` or `feature/pipeline`

---

### 4. **Node Version**
**What it is**: The version of Node.js for your build

**Example values**:
- `20` (Node 20 - latest LTS)
- `18` (Node 18 - previous LTS)
- `16` (Node 16 - older version)
- `22` (Node 22 - latest)

**Choose based on your project**:
- **Angular 18+**: Use Node 20 or 22
- **Angular 16-17**: Use Node 18 or 20
- **Older projects**: Node 16

**For PACTLINE (Angular)**: `20`

---

### 5. **SonarQube Project Key** (Optional)
**What it is**: Your SonarQube project key for code quality analysis

**Example values**:
- `PrathamM16_PACTLINE` (for PACTLINE)
- `owner_projectname`
- Leave empty if you don't use SonarQube

**How to find it**:
1. Visit SonarQube dashboard: https://sonarcloud.io
2. Go to your project
3. Look for the project key (usually shows in settings)

**Format**: `ORGANIZATION_PROJECTNAME` (replace spaces with underscore)

**For PACTLINE**: `PrathamM16_PACTLINE`

---

## Complete Example for PACTLINE

Fill in the form like this:

```
Job Name:                 pactline-ci
Repository:               PrathamM16/PACTLINE
Branch:                   feature/ci-cd
Node Version:             20
SonarQube Project Key:    PrathamM16_PACTLINE
```

---

## What Gets Generated

When you submit the form, the system creates a **Jenkinsfile** with these stages:

```
1. Checkout          → Clone your repository
2. Install Deps      → npm ci (clean install)
3. Lint              → ESLint for code quality
4. Unit Tests        → ng test for coverage
5. SonarQube         → Code quality analysis
6. Quality Gate      → Pass/fail on metrics
7. Build             → ng build for production
```

---

## Step-by-Step: Create Pipeline for PACTLINE

### Step 1: Open Pipeline Builder
- Go to http://localhost:4200
- Login with: `qa-tester@example.com` / `QaTester-12345`
- Click "Engineering" in navigation menu

### Step 2: Fill the Form
```
Job Name:              pactline-ci
Repository:            PrathamM16/PACTLINE
Branch:                feature/ci-cd
Node Version:          20
SonarQube Project Key: PrathamM16_PACTLINE
```

### Step 3: Preview Pipeline
- Click "Preview" or "Generate"
- Review the Jenkinsfile content
- Check it has all stages you need

### Step 4: Approve & Create PR
- If using voice assistant, approve the action
- System creates branch on GitHub
- Commits Jenkinsfile
- Opens Pull Request

### Step 5: Merge in GitHub
- Go to GitHub: https://github.com/PrathamM16/PACTLINE/pulls
- Review the PR
- Click "Merge pull request"
- Jenkins will automatically run the pipeline

---

## Common Configurations

### For Angular Projects
```
Job Name:              my-angular-app-ci
Repository:            username/my-angular-app
Branch:                feature/add-cicd
Node Version:          20
SonarQube Key:         username_myapp
```

### For React Projects
```
Job Name:              react-app-pipeline
Repository:            username/react-app
Branch:                feature/ci-cd
Node Version:          18
SonarQube Key:         username_reactapp
```

### For Node.js API
```
Job Name:              nodejs-api-build
Repository:            username/api-service
Branch:                feature/pipeline
Node Version:          20
SonarQube Key:         username_api
```

---

## Tips & Tricks

### Branch Naming
- **Feature**: `feature/ci-cd`, `feature/pipeline`, `feature/devops`
- **Bug Fix**: `bugfix/jenkins-setup`
- **Release**: `release/v1.0.0`

### Job Naming
- Use descriptive names: `pactline-ci`, `angular-build`, `frontend-test`
- Avoid special characters except hyphen and underscore
- Keep it short but clear: 1-3 words

### Node Version Selection
- Check your `package.json` for `engines.node`
- If not specified, use latest LTS (20 or 22)
- Match your local development version

### SonarQube Integration
- Leave empty if you don't have SonarQube
- Pipeline still works without it
- You can add it later in the Jenkinsfile

---

## Troubleshooting

### "Repository not found"
**Cause**: Repository path is incorrect
**Fix**: Use format `username/reponame` exactly as shown on GitHub
- ✅ Correct: `PrathamM16/PACTLINE`
- ❌ Wrong: `PrathamM16-PACTLINE` or `PACTLINE` or `github.com/PrathamM16/PACTLINE`

### "Invalid branch name"
**Cause**: Special characters in branch name
**Fix**: Use only lowercase letters, numbers, hyphens, underscores
- ✅ Correct: `feature/ci-cd`, `feature_pipeline`, `main`
- ❌ Wrong: `Feature/CI-CD`, `feature CI/CD`, `feature@pipeline`

### "Node version not found"
**Cause**: Invalid Node.js version
**Fix**: Use exact version numbers like 16, 18, 20, 22
- ✅ Correct: `20`, `18`, `16`
- ❌ Wrong: `20.0.0`, `v20`, `node20`, `latest`

### "SonarQube project not found"
**Cause**: Project key is incorrect or project is private
**Fix**: 
1. Verify project key at https://sonarcloud.io
2. Ensure project is Public
3. Leave empty if not using SonarQube

---

## Example: Real PACTLINE Setup

For the PACTLINE project being developed:

| Field | Value | Reason |
|-------|-------|--------|
| Job Name | `pactline-ci` | Descriptive, matches project |
| Repository | `PrathamM16/PACTLINE` | Exact GitHub path |
| Branch | `feature/ci-cd` | Feature branch for CI/CD setup |
| Node Version | `20` | Latest LTS, good for Angular |
| SonarQube Key | `PrathamM16_PACTLINE` | Existing project on SonarQube |

**Result**: Pipeline with lint → test → SonarQube → build → quality gate

---

## Next Steps After Creating Pipeline

1. **Review Generated Jenkinsfile**
   - Check all stages are present
   - Verify Node version is correct
   - Confirm SonarQube project key

2. **Approve in Voice Assistant** (if using voice)
   - Review the PR content
   - Click "Approve" button

3. **Merge Pull Request on GitHub**
   - Go to your GitHub repository
   - Find the new PR with Jenkinsfile
   - Click "Merge pull request"

4. **Jenkins Triggers Automatically**
   - Jenkins runs the pipeline
   - Build artifacts created
   - SonarQube analysis completes
   - Quality gate passes/fails

5. **Monitor Build Results**
   - Check Jenkins: http://localhost:8080
   - View SonarQube: https://sonarcloud.io
   - See build logs in Jenkins UI

---

## Need Help?

If you're stuck:

1. **For repository format**: Check the GitHub URL bar - should be `github.com/OWNER/REPO`
2. **For branch names**: Use `feature/something` format
3. **For Node version**: Use same version as your `package.json` or latest LTS (20)
4. **For SonarQube**: Visit https://sonarcloud.io to find your project key

**Example Quick Answers**:
- Q: "What do I put for repository?" → A: `PrathamM16/PACTLINE`
- Q: "What Node version?" → A: `20`
- Q: "What branch?" → A: `feature/ci-cd`
- Q: "Is SonarQube required?" → A: No, it's optional

---

**Version**: 0.4.0  
**Status**: Ready to Use  
**Last Updated**: November 2026
