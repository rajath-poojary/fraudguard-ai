from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EventUpdate(BaseModel):
    event_id: str
    event_type: str
    created_at: datetime
    transaction_id: UUID | None = None
    alert_id: UUID | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    decision: str | None = None
    reason: str | None = None


class EventPollResponse(BaseModel):
    events: list[EventUpdate] = Field(default_factory=list)
    server_time: datetime
    next_since: datetime