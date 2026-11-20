from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from uuid import uuid4

from app.storage import Database, Store


class ConfirmationStatus(str, Enum):
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"


class CommitmentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


def _date(value):
    return date.fromisoformat(value) if value else None


@dataclass
class HistoryEntry:
    action: str
    actor: str
    deadline: date | None
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Commitment:
    owner: str
    description: str
    deadline: date | None
    conversation_id: str
    workspace_id: str
    evidence: str
    id: str = field(default_factory=lambda: str(uuid4()))
    confirmation: ConfirmationStatus = ConfirmationStatus.SUGGESTED
    status: CommitmentStatus = CommitmentStatus.PENDING
    confirmed_by: list[str] = field(default_factory=list)
    disputed_deadlines: dict[str, date] = field(default_factory=dict)
    history: list[HistoryEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "owner": self.owner, "description": self.description, "deadline": self.deadline.isoformat() if self.deadline else None,
            "conversation_id": self.conversation_id, "workspace_id": self.workspace_id, "evidence": self.evidence, "id": self.id,
            "confirmation": self.confirmation.value, "status": self.status.value, "confirmed_by": self.confirmed_by,
            "disputed_deadlines": {k: v.isoformat() for k, v in self.disputed_deadlines.items()},
            "history": [{"action": h.action, "actor": h.actor, "deadline": h.deadline.isoformat() if h.deadline else None, "at": h.at.isoformat()} for h in self.history],
        }

    @staticmethod
    def from_dict(data: dict) -> "Commitment":
        return Commitment(
            owner=data["owner"], description=data["description"], deadline=_date(data["deadline"]), conversation_id=data["conversation_id"],
            workspace_id=data["workspace_id"], evidence=data["evidence"], id=data["id"], confirmation=ConfirmationStatus(data["confirmation"]),
            status=CommitmentStatus(data["status"]), confirmed_by=list(data["confirmed_by"]),
            disputed_deadlines={k: date.fromisoformat(v) for k, v in data["disputed_deadlines"].items()},
            history=[HistoryEntry(h["action"], h["actor"], _date(h["deadline"]), datetime.fromisoformat(h["at"])) for h in data["history"]],
        )


class CommitmentLedger:
    def __init__(self, store: Store | None = None):
        if store is None:
            db = Database("sqlite:///:memory:")
            db.migrate()
            store = Store(db)
        self._store = store

    def _save(self, item: Commitment) -> Commitment:
        self._store.put("commitment", item.workspace_id, item.id, item.to_dict())
        return item

    def propose(self, owner, description, deadline, conversation_id, workspace_id, evidence, actor) -> Commitment:
        item = Commitment(owner, description, deadline, conversation_id, workspace_id, evidence)
        item.history.append(HistoryEntry("proposed", actor, deadline))
        return self._save(item)

    def get(self, commitment_id: str, workspace_id: str) -> Commitment:
        data = self._store.get("commitment", workspace_id, commitment_id)
        if data is None:
            raise PermissionError("commitment not found in this workspace")
        return Commitment.from_dict(data)

    def dispute(self, commitment_id, workspace_id, actor, claimed_deadline) -> Commitment:
        item = self.get(commitment_id, workspace_id)
        if claimed_deadline == item.deadline:
            return item
        item.disputed_deadlines[actor] = claimed_deadline
        item.confirmation = ConfirmationStatus.DISPUTED
        item.history.append(HistoryEntry("disputed", actor, claimed_deadline))
        return self._save(item)

    def confirm(self, commitment_id, workspace_id, actor) -> Commitment:
        item = self.get(commitment_id, workspace_id)
        if item.confirmation is ConfirmationStatus.DISPUTED:
            raise ValueError("resolve the disputed deadline before confirming")
        if actor not in item.confirmed_by:
            item.confirmed_by.append(actor)
        item.confirmation = ConfirmationStatus.CONFIRMED
        item.history.append(HistoryEntry("confirmed", actor, item.deadline))
        return self._save(item)

    def resolve(self, commitment_id, workspace_id, actor, agreed_deadline) -> Commitment:
        item = self.get(commitment_id, workspace_id)
        item.deadline = agreed_deadline
        item.disputed_deadlines.clear()
        item.confirmation = ConfirmationStatus.CONFIRMED
        if actor not in item.confirmed_by:
            item.confirmed_by.append(actor)
        item.history.append(HistoryEntry("resolved", actor, agreed_deadline))
        return self._save(item)

    def complete(self, commitment_id, workspace_id, actor) -> Commitment:
        item = self.get(commitment_id, workspace_id)
        item.status = CommitmentStatus.COMPLETED
        item.history.append(HistoryEntry("completed", actor, item.deadline))
        return self._save(item)

    def _all(self, workspace_id: str) -> list[Commitment]:
        return [Commitment.from_dict(d) for d in self._store.list_records("commitment", workspace_id)]

    def conflicts(self, workspace_id: str) -> list[Commitment]:
        return [c for c in self._all(workspace_id) if c.confirmation is ConfirmationStatus.DISPUTED]

    def pending(self, workspace_id: str, owner: str | None = None) -> list[Commitment]:
        return [c for c in self._all(workspace_id) if c.status is CommitmentStatus.PENDING and (owner is None or c.owner == owner)]

    def overdue(self, workspace_id: str, today: date) -> list[Commitment]:
        return [c for c in self.pending(workspace_id) if c.deadline is not None and c.deadline < today]

    def is_ready_for_execution(self, commitment: Commitment) -> bool:
        return commitment.confirmation is ConfirmationStatus.CONFIRMED and commitment.deadline is not None
