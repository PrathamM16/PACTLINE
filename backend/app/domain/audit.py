from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class AuditEvent:
    actor: str
    action: str
    resource: str
    outcome: str
    detail: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLog:
    def __init__(self):
        self.events: list[AuditEvent] = []

    def record(self, actor, action, resource, outcome, detail="") -> AuditEvent:
        event = AuditEvent(actor, action, resource, outcome, detail)
        self.events.append(event)
        return event
