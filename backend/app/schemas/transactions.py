from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionCreate(BaseModel):
    transaction_id: UUID | None = None
    user_id: UUID | None = None
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timestamp: datetime | None = None
    merchant_id: UUID | None = None
    merchant_category: str | None = Field(default=None, max_length=100)
    device_id: UUID | None = None
    device_fingerprint: str | None = Field(default=None, max_length=255)
    device_status: str = Field(default="known", pattern="^(known|new)$")
    ip_address: str | None = Field(default=None, max_length=45)
    location: str | None = Field(default=None, max_length=100)
    merchant: str | None = Field(default=None, max_length=200)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    account_age: int | None = Field(default=None, ge=0)
    payment_method: str | None = Field(default=None, max_length=50)
    transaction_status: str | None = Field(default="pending", max_length=30)
    previous_transaction_id: UUID | None = None
    is_fraud: bool = False
    fraud_scenario: str | None = Field(default=None, max_length=50)
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
    expected_loss: float = 0.0
    risk_score: float
    risk_level: str
    decision: str
    reasons: list[str]
    evidence: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    explanation: dict[str, Any] = Field(default_factory=dict)
    contributions: list[dict[str, Any]] = Field(default_factory=list)
    rule_matches: list[dict[str, Any]] = Field(default_factory=list)


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_id: UUID | None = None
    user_id: UUID
    amount: Decimal
    currency: str
    status: str
    transaction_status: str | None = None
    occurred_at: datetime
    timestamp: datetime | None = None
    merchant_id: UUID | None = None
    merchant_category: str | None = None
    device_id: UUID | None = None
    ip_address: str | None = None
    location: str | None = None
    account_age: int | None = None
    payment_method: str | None = None
    previous_transaction_id: UUID | None = None
    is_fraud: bool = False
    fraud_scenario: str | None = None
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
    total_volume: float = 0.0
    exposure_prevented: float = 0.0
    active_investigations: int = 0
    model_health: dict[str, str] = Field(default_factory=dict)
    top_risky_merchants: list[dict[str, Any]] = Field(default_factory=list)
    top_risky_devices: list[dict[str, Any]] = Field(default_factory=list)
    fraud_trend: list[dict[str, Any]] = Field(default_factory=list)
    system_status: str = "OPERATIONAL"
    transactions_per_minute: float = 0.0
    current_fraud_rate: float = 0.0
    financial_exposure: float = 0.0
    critical_alerts: list[dict[str, Any]] = Field(default_factory=list)
    top_risky_users: list[dict[str, Any]] = Field(default_factory=list)
    suspicious_ips: list[dict[str, Any]] = Field(default_factory=list)
    detection_stream: list[dict[str, Any]] = Field(default_factory=list)


class SimulationResponse(BaseModel):
    transaction: TransactionResponse


class AttackSimulationRequest(BaseModel):
    attack_type: str = Field(pattern="^(normal|account_takeover|card_testing|velocity|device_takeover|impossible_travel|coordinated_fraud|merchant_abuse|fraud_ring)$")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    base_location: str = Field(default="Bengaluru", min_length=2, max_length=100)
    base_amount: Decimal = Field(default=Decimal("1200"), gt=0, max_digits=18, decimal_places=2)

    @field_validator("currency")
    @classmethod
    def normalize_attack_currency(cls, value: str) -> str:
        return value.upper()


class AttackSimulationEvent(BaseModel):
    event_id: str
    offset_seconds: int
    label: str
    event_type: str
    transaction_id: UUID | None = None
    amount: float | None = None
    risk_score: float | None = None
    fraud_probability: float | None = None
    decision: str | None = None
    risk_level: str | None = None
    detected: bool = False
    signals: list[str] = Field(default_factory=list)


class AttackSimulationResponse(BaseModel):
    attack_type: str
    transactions_generated: int
    fraudulent_transactions: int
    detected_transactions: int
    missed_transactions: int
    blocked_transactions: int
    reviewed_transactions: int
    detection_rate: float
    peak_risk_score: float
    detected: bool
    detection_time_seconds: int | None = None
    average_detection_time_seconds: float | None = None
    financial_exposure: float
    financial_exposure_prevented: float
    events: list[AttackSimulationEvent]
    transactions: list[TransactionResponse]
