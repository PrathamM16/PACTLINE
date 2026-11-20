import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable
from uuid import uuid4

from app.domain.approval import requires_approval


class WorkflowState(str, Enum):
    DRAFT = "DRAFT"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    APPROVED = "APPROVED"
    RUNNING = "RUNNING"
    WAITING_FOR_EXTERNAL_EVENT = "WAITING_FOR_EXTERNAL_EVENT"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


S = WorkflowState

TRANSITIONS = {
    S.DRAFT: {S.CLARIFICATION_REQUIRED, S.READY_FOR_APPROVAL, S.APPROVED, S.CANCELLED},
    S.CLARIFICATION_REQUIRED: {S.DRAFT, S.READY_FOR_APPROVAL, S.CANCELLED},
    S.READY_FOR_APPROVAL: {S.APPROVED, S.CANCELLED},
    S.APPROVED: {S.RUNNING, S.CANCELLED},
    S.RUNNING: {S.WAITING_FOR_EXTERNAL_EVENT, S.COMPLETED, S.PARTIALLY_COMPLETED, S.FAILED, S.CANCELLED},
    S.WAITING_FOR_EXTERNAL_EVENT: {S.RUNNING, S.COMPLETED, S.FAILED, S.CANCELLED},
    S.COMPLETED: set(),
    S.PARTIALLY_COMPLETED: set(),
    S.FAILED: set(),
    S.CANCELLED: set(),
}

WAIT = object()


class InvalidTransition(Exception):
    pass


@dataclass
class Step:
    name: str
    tool: str
    handler: Callable[[], object]
    max_attempts: int = 1
    status: str = "pending"
    result: object = None
    error: str | None = None
    attempts: int = 0


@dataclass
class Workflow:
    user_id: str
    workspace_id: str
    conversation_id: str
    intent: str
    steps: list[Step]
    id: str = field(default_factory=lambda: str(uuid4()))
    state: WorkflowState = WorkflowState.DRAFT
    completed_keys: set = field(default_factory=set)
    state_log: list[WorkflowState] = field(default_factory=lambda: [WorkflowState.DRAFT])

    def transition(self, target: WorkflowState) -> None:
        if target not in TRANSITIONS[self.state]:
            raise InvalidTransition(f"{self.state.value} -> {target.value}")
        self.state = target
        self.state_log.append(target)

    def needs_approval(self) -> bool:
        return any(requires_approval(step.tool) for step in self.steps)

    def submit(self) -> None:
        self.transition(S.READY_FOR_APPROVAL if self.needs_approval() else S.APPROVED)

    def approve(self) -> None:
        self.transition(S.APPROVED)

    def cancel(self) -> None:
        self.transition(S.CANCELLED)

    def run(self) -> WorkflowState:
        if self.state is S.APPROVED:
            self.transition(S.RUNNING)
        elif self.state is not S.RUNNING:
            raise InvalidTransition(f"cannot run from {self.state.value}")
        for step in self.steps:
            if step.status == "done":
                continue
            outcome = self._execute(step)
            if outcome is WAIT:
                self.transition(S.WAITING_FOR_EXTERNAL_EVENT)
                return self.state
            if step.status == "failed":
                done = any(s.status == "done" for s in self.steps)
                self.transition(S.PARTIALLY_COMPLETED if done else S.FAILED)
                return self.state
        self.transition(S.COMPLETED)
        return self.state

    def resume(self, step_name: str, result: object) -> WorkflowState:
        if self.state is not S.WAITING_FOR_EXTERNAL_EVENT:
            raise InvalidTransition("workflow is not waiting")
        step = next(s for s in self.steps if s.name == step_name)
        step.status = "done"
        step.result = result
        self.transition(S.RUNNING)
        return self.run()

    def _execute(self, step: Step):
        key = f"{self.id}:{step.name}"
        if key in self.completed_keys:
            step.status = "done"
            return step.result
        while step.attempts < step.max_attempts:
            step.attempts += 1
            try:
                outcome = step.handler()
            except Exception as exc:
                step.error = str(exc)
                continue
            if outcome is WAIT:
                step.status = "waiting"
                return WAIT
            step.status = "done"
            step.result = outcome
            step.error = None
            self.completed_keys.add(key)
            return outcome
        step.status = "failed"
        return None
