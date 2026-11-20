from dataclasses import dataclass

from app.devops.pipeline import PipelineSpec, generate_jenkinsfile, validate_jenkinsfile, validate_spec
from app.domain.approval import ApprovalGate
from app.domain.audit import AuditLog
from app.integrations.jenkins import JenkinsClient, JenkinsError, job_config_xml


@dataclass
class ToolResult:
    ok: bool
    detail: str
    data: dict | None = None


class DevopsTools:
    def __init__(self, jenkins: JenkinsClient, approvals: ApprovalGate, audit: AuditLog, allowed_repositories: set, allowed_jobs: set):
        self._jenkins = jenkins
        self._approvals = approvals
        self._audit = audit
        self._repositories = allowed_repositories
        self._jobs = allowed_jobs

    def generate_jenkinsfile(self, actor: str, spec: PipelineSpec) -> ToolResult:
        errors = validate_spec(spec)
        if errors:
            self._audit.record(actor, "generate_jenkinsfile", spec.job_name, "rejected", "; ".join(errors))
            return ToolResult(False, "; ".join(errors))
        content = generate_jenkinsfile(spec)
        problems = validate_jenkinsfile(content)
        if problems:
            self._audit.record(actor, "generate_jenkinsfile", spec.job_name, "rejected", "; ".join(problems))
            return ToolResult(False, "; ".join(problems))
        self._audit.record(actor, "generate_jenkinsfile", spec.job_name, "generated")
        return ToolResult(True, "generated", {"jenkinsfile": content})

    def create_jenkins_job(self, actor: str, spec: PipelineSpec, approval_id: str) -> ToolResult:
        if spec.repository not in self._repositories or spec.job_name not in self._jobs:
            self._audit.record(actor, "create_jenkins_job", spec.job_name, "denied", "not in allowlist")
            return ToolResult(False, "repository or job is not allowlisted")
        if not self._approvals.is_approved(approval_id, "create_jenkins_job", spec.job_name):
            self._audit.record(actor, "create_jenkins_job", spec.job_name, "denied", "missing approval")
            return ToolResult(False, "explicit approval required")
        try:
            outcome = self._jenkins.create_job(spec.job_name, job_config_xml(spec))
        except JenkinsError as exc:
            self._audit.record(actor, "create_jenkins_job", spec.job_name, "failed", str(exc))
            return ToolResult(False, str(exc))
        if not outcome["confirmed"]:
            self._audit.record(actor, "create_jenkins_job", spec.job_name, "unconfirmed")
            return ToolResult(False, "Jenkins accepted the request but the job could not be confirmed")
        self._audit.record(actor, "create_jenkins_job", spec.job_name, "confirmed")
        return ToolResult(True, "job confirmed by Jenkins", outcome)

    def trigger_build(self, actor: str, job_name: str, approval_id: str) -> ToolResult:
        if job_name not in self._jobs:
            return ToolResult(False, "job is not allowlisted")
        if not self._approvals.is_approved(approval_id, "trigger_jenkins_build", job_name):
            self._audit.record(actor, "trigger_jenkins_build", job_name, "denied", "missing approval")
            return ToolResult(False, "explicit approval required")
        try:
            self._jenkins.trigger_build(job_name)
        except JenkinsError as exc:
            self._audit.record(actor, "trigger_jenkins_build", job_name, "failed", str(exc))
            return ToolResult(False, str(exc))
        self._audit.record(actor, "trigger_jenkins_build", job_name, "queued")
        return ToolResult(True, "build queued")
