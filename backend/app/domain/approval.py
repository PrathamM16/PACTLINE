import re
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class Risk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


TOOL_RISK = {
    "retrieve_calendar_events": Risk.LOW,
    "retrieve_commitments": Risk.LOW,
    "list_github_repositories": Risk.LOW,
    "get_jenkins_build_status": Risk.LOW,
    "get_sonar_quality_gate": Risk.LOW,
    "create_task": Risk.MEDIUM,
    "create_calendar_event": Risk.MEDIUM,
    "create_shopping_list": Risk.MEDIUM,
    "generate_jenkinsfile": Risk.MEDIUM,
    "create_github_branch": Risk.MEDIUM,
    "create_github_pull_request": Risk.MEDIUM,
    "create_jenkins_job": Risk.HIGH,
    "update_jenkins_job": Risk.HIGH,
    "trigger_jenkins_build": Risk.HIGH,
    "merge_pull_request": Risk.HIGH,
    "create_service_request": Risk.HIGH,
}

EXPLICIT_PHRASES = {
    "yes",
    "yes approve",
    "yes approved",
    "approve",
    "approved",
    "yes create it",
    "yes go ahead",
    "go ahead",
    "confirm",
    "confirmed",
    "yes confirm",
}

HEDGES = re.compile(r"\b(maybe|not|don't|dont|no|wait|unsure|guess|think|probably|later)\b")


def classify(tool_name: str) -> Risk:
    return TOOL_RISK.get(tool_name, Risk.HIGH)


def requires_approval(tool_name: str) -> bool:
    return classify(tool_name) is not Risk.LOW


def is_explicit_approval(utterance: str) -> bool:
    normalized = re.sub(r"[^a-z' ]", "", utterance.lower()).strip()
    if HEDGES.search(normalized):
        return False
    return normalized in EXPLICIT_PHRASES


@dataclass
class ApprovalRequest:
    tool: str
    resource: str
    params: dict
    reversible: bool
    requested_by: str
    risk: Risk
    id: str = field(default_factory=lambda: str(uuid4()))
    approved: bool | None = None
    decided_by: str | None = None


class ApprovalGate:
    def __init__(self):
        self._requests: dict[str, ApprovalRequest] = {}

    def request(self, tool, resource, params, reversible, requested_by) -> ApprovalRequest:
        item = ApprovalRequest(tool, resource, dict(params), reversible, requested_by, classify(tool))
        self._requests[item.id] = item
        return item

    def decide(self, approval_id: str, decided_by: str, approved: bool) -> ApprovalRequest:
        item = self._requests[approval_id]
        if item.approved is not None:
            raise ValueError("approval already decided")
        item.approved = approved
        item.decided_by = decided_by
        return item

    def is_approved(self, approval_id: str, tool: str, resource: str) -> bool:
        item = self._requests.get(approval_id)
        return bool(item) and item.approved is True and item.tool == tool and item.resource == resource
