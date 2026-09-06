from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.transactions import TransactionResponse


ActionType = Literal["ASSIGN", "ADD_NOTE", "MARK_INVESTIGATING", "CONFIRM_FRAUD", "MARK_FALSE_POSITIVE", "MARK_UNCERTAIN", "RESOLVE"]


class InvestigationSummary(BaseModel):
    id: UUID
    alert_id: UUID
    transaction_id: UUID
    title: str
    severity: str
    status: str
    assigned_to: str | None = None
    action_count: int = 0
    created_at: datetime


class InvestigatorActionCreate(BaseModel):
    action_type: ActionType
    note: str | None = Field(default=None, max_length=4000)
    assigned_to_id: UUID | None = None


class InvestigationActionResponse(BaseModel):
    id: UUID
    action_type: str
    actor_user_id: UUID
    actor_name: str
    note: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class InvestigationTimelineItem(BaseModel):
    timestamp: datetime
    source: Literal["alert", "risk_event", "investigator_action"]
    label: str
    detail: str
    linked_id: UUID | None = None
    risk_score: float | None = None


class InvestigationCaseResponse(BaseModel):
    id: UUID
    alert_id: UUID
    status: str
    title: str
    assigned_to: str | None = None
    alert: dict[str, Any]
    transaction: TransactionResponse
    user: dict[str, Any]
    behavior_profile: dict[str, Any] | None = None
    device: dict[str, Any] | None = None
    ip: dict[str, Any] | None = None
    merchant: dict[str, Any] | None = None
    related_transactions: list[TransactionResponse] = Field(default_factory=list)
    network: dict[str, Any] = Field(default_factory=dict)
    risk_history: list[dict[str, Any]] = Field(default_factory=list)
    ml_explanation: dict[str, Any] = Field(default_factory=dict)
    anomaly_evidence: list[dict[str, Any]] = Field(default_factory=list)
    velocity_evidence: list[dict[str, Any]] = Field(default_factory=list)
    rule_evidence: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[InvestigationTimelineItem] = Field(default_factory=list)
    actions: list[InvestigationActionResponse] = Field(default_factory=list)