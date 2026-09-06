from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import canonical_role, require_permission
from app.models import FraudAlert, Transaction, User
from app.schemas.events import EventPollResponse, EventUpdate

router = APIRouter(prefix="/events", tags=["events"])


def _ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@router.get("/poll", response_model=EventPollResponse)
def poll_events(
    since: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics_read")),
) -> EventPollResponse:
    server_time = datetime.now(timezone.utc)
    cursor = since or datetime.fromtimestamp(0, timezone.utc)
    query = select(Transaction).where(Transaction.created_at > cursor).order_by(Transaction.created_at.asc()).limit(200)
    if canonical_role(getattr(user, "role", "user")) != "ADMIN":
        query = query.where(Transaction.user_id == user.id)
    transactions = list(db.scalars(query).all())
    transaction_ids = [item.id for item in transactions]
    alerts = list(db.scalars(select(FraudAlert).where(FraudAlert.transaction_id.in_(transaction_ids))).all()) if transaction_ids else []
    alert_by_transaction = {item.transaction_id: item for item in alerts}
    events = [
        EventUpdate(
            event_id=f"transaction:{item.id}", event_type="transaction_analyzed", created_at=item.created_at,
            transaction_id=item.id, alert_id=alert_by_transaction[item.id].id if item.id in alert_by_transaction else None,
            risk_score=float(item.risk_score) if item.risk_score is not None else None, risk_level=item.risk_level,
            decision=item.decision, reason=(item.reasons or [None])[0],
        )
        for item in transactions
    ]
    events.extend(EventUpdate(event_id=f"alert:{item.id}", event_type="fraud_alert_created", created_at=item.created_at, transaction_id=item.transaction_id, alert_id=item.id, risk_score=float(item.risk_score), reason=item.reason_code) for item in alerts if _ensure_utc(item.created_at) > cursor)
    events.sort(key=lambda item: item.created_at)
    return EventPollResponse(events=events, server_time=server_time, next_since=server_time)