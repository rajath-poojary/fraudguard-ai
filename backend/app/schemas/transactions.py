from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    merchant_id: UUID | None = None
    device_id: UUID | None = None
    device_fingerprint: str | None = Field(default=None, max_length=255)
    device_status: str = Field(default="known", pattern="^(known|new)$")
    location: str | None = Field(default=None, max_length=100)
    merchant: str | None = Field(default=None, max_length=200)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("device_status")
    @classmethod
    def normalize_device_status(cls, value: str) -> str:
        return value.lower()


class TransactionAnalysis(BaseModel):
    fraud_probability: float
    anomaly_score: float
    risk_score: float
    risk_level: str
    decision: str
    reasons: list[str]
    contributions: list[dict[str, Any]] = Field(default_factory=list)
    rule_matches: list[dict[str, Any]] = Field(default_factory=list)


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    amount: Decimal
    currency: str
    status: str
    occurred_at: datetime
    analysis: TransactionAnalysis | None = None
    created_at: datetime


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int


class FraudAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_id: UUID
    user_id: UUID
    risk_score: Decimal
    status: str
    reason_code: str
    created_at: datetime


class FraudAlertListResponse(BaseModel):
    items: list[FraudAlertResponse]
    total: int


class DashboardStatistics(BaseModel):
    total_transactions: int
    total_alerts: int
    high_risk_transactions: int
    review_transactions: int
    blocked_transactions: int
    approved_transactions: int
    risk_distribution: dict[str, int] = Field(default_factory=dict)
    fraud_rate: float = 0.0
    model_health: dict[str, str] = Field(default_factory=dict)


class SimulationResponse(BaseModel):
    transaction: TransactionResponse


class AttackSimulationRequest(BaseModel):
    attack_type: str = Field(pattern="^(normal|account_takeover|card_testing|velocity|impossible_travel|device_takeover|fraud_ring)$")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    base_location: str = Field(default="Bengaluru", min_length=2, max_length=100)
    base_amount: Decimal = Field(default=Decimal("1200"), gt=0, max_digits=18, decimal_places=2)

    @field_validator("currency")
    @classmethod
    def normalize_attack_currency(cls, value: str) -> str:
        return value.upper()


class AttackSimulationResponse(BaseModel):
    attack_type: str
    transactions_generated: int
    detected_transactions: int
    detection_rate: float
    peak_risk_score: float
    detected: bool
    transactions: list[TransactionResponse]
