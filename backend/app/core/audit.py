from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record_audit(
    db: Session,
    event_type: str,
    actor: User | None,
    resource_type: str,
    resource_id: UUID | str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        event_type=event_type,
        actor_user_id=actor.id if actor else None,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        details=details or {},
    )
    db.add(entry)
    return entry