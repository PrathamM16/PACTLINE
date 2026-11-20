from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.errors import ProviderError
from app.storage import Store

MAX_ATTEMPTS = 3


def to_utc(value: str, tz_name: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    aware = parsed if parsed.tzinfo else parsed.replace(tzinfo=ZoneInfo(tz_name))
    return aware.astimezone(timezone.utc)


def deliver_due(store: Store, mailer, now: datetime, tz_name: str) -> dict:
    result = {"sent": 0, "failed": 0}
    if mailer is None:
        return result
    for workspace_id, record in store.list_all("reminder"):
        attempts = record.get("attempts", 0)
        if record["delivery"] not in ("pending", "failed") or attempts >= MAX_ATTEMPTS or to_utc(record["remind_at"], tz_name) > now:
            continue
        attempt = attempts + 1
        if not store.once(f"reminder:{record['id']}:{attempt}"):
            continue
        try:
            if not record.get("recipient_email"):
                raise ProviderError("no recipient email on record")
            mailer.send(record["recipient_email"], "Reminder: " + record["text"][:80], f"{record['text']}\n\nScheduled in PACTLINE for {record['remind_at']}.")
        except ProviderError as exc:
            record.update(delivery="failed", attempts=attempt, error=str(exc)[:200])
            result["failed"] += 1
            store.audit(workspace_id, "system", "reminder_delivery", record["id"], "failed", str(exc))
        else:
            record.update(delivery="sent", attempts=attempt, sent_at=now.isoformat(), error=None)
            result["sent"] += 1
            store.audit(workspace_id, "system", "reminder_delivery", record["id"], "sent")
        store.put("reminder", workspace_id, record["id"], record)
    return result
