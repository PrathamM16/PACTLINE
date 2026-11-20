import re
from dataclasses import dataclass

STAGE_ORDER = (
    "checkout",
    "environment",
    "install",
    "lint",
    "unit_tests",
    "sonar_analysis",
    "quality_gate",
    "build",
)

STAGE_TITLES = {
    "checkout": "Checkout",
    "environment": "Environment Validation",
    "install": "Install Dependencies",
    "lint": "Lint",
    "unit_tests": "Unit Tests",
    "sonar_analysis": "SonarQube Analysis",
    "quality_gate": "Quality Gate",
    "build": "Production Build",
}

SHELL_COMMANDS = {
    "environment": "node --version && npm --version",
    "install": "npm ci",
    "lint": "npm run lint",
    "unit_tests": "npm run test -- --watch=false --browsers=ChromeHeadless",
    "build": "npm run build -- --configuration production",
}

REQUIRES = {
    "lint": {"install"},
    "unit_tests": {"install"},
    "sonar_analysis": {"install"},
    "quality_gate": {"sonar_analysis"},
    "build": {"install"},
}

JOB_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,100}$")
NODE_RE = re.compile(r"^\d{1,2}(\.\d{1,3}){0,2}$")
SONAR_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
SUPPORTED_APP_TYPES = {"angular"}


@dataclass(frozen=True)
class PipelineSpec:
    job_name: str
    repository: str
    branch: str
    app_type: str
    node_version: str
    stages: tuple
    sonar_project_key: str | None = None
    git_credentials_id: str | None = None


def validate_spec(spec: PipelineSpec) -> list[str]:
    errors = []
    if not JOB_NAME_RE.match(spec.job_name):
        errors.append("invalid job name")
    if not REPOSITORY_RE.match(spec.repository):
        errors.append("invalid repository, expected owner/name")
    if not BRANCH_RE.match(spec.branch) or ".." in spec.branch:
        errors.append("invalid branch")
    if spec.app_type not in SUPPORTED_APP_TYPES:
        errors.append("unsupported application type")
    if not NODE_RE.match(spec.node_version):
        errors.append("invalid node version")
    unknown = set(spec.stages) - set(STAGE_ORDER)
    if unknown:
        errors.append("unknown stages: " + ", ".join(sorted(unknown)))
    chosen = set(spec.stages)
    for stage in chosen & set(REQUIRES):
        missing = REQUIRES[stage] - chosen
        if missing:
            errors.append(f"{stage} requires {', '.join(sorted(missing))}")
    if "sonar_analysis" in chosen and not (spec.sonar_project_key and SONAR_KEY_RE.match(spec.sonar_project_key)):
        errors.append("sonar_analysis requires a valid sonar project key")
    return errors


def _ordered(spec: PipelineSpec) -> list[str]:
    chosen = set(spec.stages) | {"checkout"}
    return [stage for stage in STAGE_ORDER if stage in chosen]


def _stage_block(stage: str, spec: PipelineSpec) -> str:
    title = STAGE_TITLES[stage]
    if stage == "checkout":
        body = "checkout scm"
    elif stage == "sonar_analysis":
        body = (
            "script {\n"
            "                    def scannerHome = tool 'SonarScanner'\n"
            "                    withSonarQubeEnv('SonarCloud') {\n"
            f"                        sh \"${{scannerHome}}/bin/sonar-scanner -Dsonar.projectKey={spec.sonar_project_key}\"\n"
            "                    }\n"
            "                }"
        )
    elif stage == "quality_gate":
        body = "timeout(time: 10, unit: 'MINUTES') {\n                    waitForQualityGate abortPipeline: true\n                }"
    else:
        body = f"sh '{SHELL_COMMANDS[stage]}'"
    return f"        stage('{title}') {{\n            steps {{\n                {body}\n            }}\n        }}\n"


def generate_jenkinsfile(spec: PipelineSpec) -> str:
    errors = validate_spec(spec)
    if errors:
        raise ValueError("; ".join(errors))
    major = spec.node_version.split(".")[0]
    stages = "".join(_stage_block(stage, spec) for stage in _ordered(spec))
    return (
        "pipeline {\n"
        "    agent any\n"
        "    options {\n"
        "        timeout(time: 30, unit: 'MINUTES')\n"
        "        disableConcurrentBuilds()\n"
        "    }\n"
        "    tools {\n"
        f"        nodejs 'NodeJS-{major}'\n"
        "    }\n"
        "    triggers {\n"
        "        githubPush()\n"
        "    }\n"
        "    stages {\n"
        f"{stages}"
        "    }\n"
        "}\n"
    )


SH_PATTERN = re.compile(r"\bsh\s+([\"'])(.*?)\1")
ALLOWED_SH = [
    re.compile(r"^" + re.escape(command) + r"$") for command in SHELL_COMMANDS.values()
] + [re.compile(r"^\$\{scannerHome\}/bin/sonar-scanner -Dsonar\.projectKey=[A-Za-z0-9._:-]+$")]
FORBIDDEN_TOKENS = ("curl", "wget", "eval", "rm -rf", "sudo", "withCredentials", "credentials(", "bash -c", "nc ", "base64")


def validate_jenkinsfile(content: str) -> list[str]:
    errors = []
    stripped = content.strip()
    if not stripped.startswith("pipeline {"):
        errors.append("must be a declarative pipeline")
    if stripped.count("{") != stripped.count("}"):
        errors.append("unbalanced braces")
    if "stages {" not in stripped:
        errors.append("missing stages block")
    for token in FORBIDDEN_TOKENS:
        if token in stripped:
            errors.append(f"forbidden token: {token.strip()}")
    for _, command in SH_PATTERN.findall(stripped):
        if not any(pattern.match(command) for pattern in ALLOWED_SH):
            errors.append(f"command not in allowlist: {command}")
    return errors
