from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("length(trim(email)) > 3", name="ck_users_email_not_blank"),
        CheckConstraint("role IN ('ADMIN', 'INVESTIGATOR', 'ANALYST')", name="ck_users_role"),
        Index("ix_users_created_at", "created_at"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="INVESTIGATOR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    devices: Mapped[list["Device"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
    fraud_alerts: Mapped[list["FraudAlert"]] = relationship(back_populates="user")
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="user")
    investigation_cases: Mapped[list["InvestigationCase"]] = relationship(back_populates="assigned_to")
    case_actions: Mapped[list["CaseAction"]] = relationship(back_populates="actor")
    investigation_feedback: Mapped[list["InvestigationFeedback"]] = relationship(back_populates="reviewer")


class Merchant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "merchants"
    __table_args__ = (
        UniqueConstraint("external_id", name="uq_merchants_external_id"),
        Index("ix_merchants_name", "name"),
    )

    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    country_code: Mapped[str | None] = mapped_column(String(2))

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="merchant")


class Device(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("user_id", "fingerprint", name="uq_devices_user_fingerprint"),
        Index("ix_devices_fingerprint", "fingerprint"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(50))
    first_seen_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    user: Mapped[User] = relationship(back_populates="devices")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="device")


class ModelVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("model_name", "version", name="uq_model_versions_name_version"),
        CheckConstraint("version > 0", name="ck_model_versions_version_positive"),
        Index("ix_model_versions_active", "model_name", "is_active"),
    )

    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    trained_at: Mapped[datetime | None] = mapped_column()

    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="model_version")


class DetectionPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "detection_policies"
    __table_args__ = (UniqueConstraint("name", name="uq_detection_policies_name"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    updated_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_transactions_amount_non_negative"),
        CheckConstraint("length(currency) = 3", name="ck_transactions_currency_iso"),
        Index("ix_transactions_user_created_at", "user_id", "created_at"),
        Index("ix_transactions_merchant_created_at", "merchant_id", "created_at"),
        Index("ix_transactions_device_created_at", "device_id", "created_at"),
        Index("ix_transactions_decision_created_at", "decision", "created_at"),
        Index("ix_transactions_ip_address_created_at", "ip_address", "created_at"),
        Index("ix_transactions_previous_tx_id", "previous_transaction_id"),
        Index("ix_transactions_is_fraud", "is_fraud"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    merchant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="SET NULL")
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    merchant_category: Mapped[str | None] = mapped_column(String(100))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    location: Mapped[str | None] = mapped_column(String(100))
    account_age: Mapped[int | None] = mapped_column(Integer)
    payment_method: Mapped[str | None] = mapped_column(String(50))
    previous_transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    is_fraud: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    fraud_scenario: Mapped[str | None] = mapped_column(String(50))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON().with_variant(JSONB, "postgresql"))
    fraud_probability: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    anomaly_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 5))
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    risk_level: Mapped[str | None] = mapped_column(String(10))
    decision: Mapped[str | None] = mapped_column(String(10))
    reasons: Mapped[list[str] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))

    user: Mapped[User] = relationship(back_populates="transactions")
    merchant: Mapped[Merchant | None] = relationship(back_populates="transactions")
    device: Mapped[Device | None] = relationship(back_populates="transactions")
    previous_transaction: Mapped["Transaction | None"] = relationship(
        remote_side="Transaction.id", foreign_keys=[previous_transaction_id]
    )
    fraud_alert: Mapped["FraudAlert | None"] = relationship(back_populates="transaction", uselist=False)
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="transaction")

    @property
    def transaction_id(self) -> UUID:
        return self.id

    @property
    def timestamp(self) -> datetime:
        return self.occurred_at

    @property
    def transaction_status(self) -> str:
        return self.status


class FraudAlert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fraud_alerts"
    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_fraud_alerts_transaction_id"),
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_fraud_alerts_score_range"),
        Index("ix_fraud_alerts_status_created_at", "status", "created_at"),
    )

    transaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open")
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column()

    transaction: Mapped[Transaction] = relationship(back_populates="fraud_alert")
    user: Mapped[User] = relationship(back_populates="fraud_alerts")
    investigation_case: Mapped["InvestigationCase | None"] = relationship(back_populates="alert", uselist=False)


class InvestigationCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investigation_cases"
    __table_args__ = (
        UniqueConstraint("alert_id", name="uq_investigation_cases_alert_id"),
        Index("ix_investigation_cases_status_created_at", "status", "created_at"),
    )

    alert_id: Mapped[UUID] = mapped_column(ForeignKey("fraud_alerts.id", ondelete="CASCADE"), nullable=False)
    assigned_to_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="OPEN")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    resolution: Mapped[str | None] = mapped_column(String(30))

    alert: Mapped[FraudAlert] = relationship(back_populates="investigation_case")
    assigned_to: Mapped[User | None] = relationship(back_populates="investigation_cases")
    actions: Mapped[list["CaseAction"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class CaseAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "case_actions"
    __table_args__ = (
        Index("ix_case_actions_case_created_at", "case_id", "created_at"),
    )

    case_id: Mapped[UUID] = mapped_column(ForeignKey("investigation_cases.id", ondelete="CASCADE"), nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))

    case: Mapped[InvestigationCase] = relationship(back_populates="actions")
    actor: Mapped[User] = relationship(back_populates="case_actions")


class InvestigationFeedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investigation_feedback"
    __table_args__ = (
        Index("ix_investigation_feedback_case_created_at", "case_id", "created_at"),
        Index("ix_investigation_feedback_label_created_at", "label", "created_at"),
    )

    case_id: Mapped[UUID] = mapped_column(ForeignKey("investigation_cases.id", ondelete="CASCADE"), nullable=False)
    transaction_id: Mapped[UUID] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False)
    reviewer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    label: Mapped[str] = mapped_column(String(30), nullable=False)
    fraud_probability: Mapped[float | None] = mapped_column(Numeric(8, 6))
    risk_score: Mapped[float | None] = mapped_column(Numeric(8, 2))
    reason_codes: Mapped[list[str] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    evidence: Mapped[list[str] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))

    case: Mapped[InvestigationCase] = relationship()
    transaction: Mapped[Transaction] = relationship()
    reviewer: Mapped[User] = relationship(back_populates="investigation_feedback")


class RiskEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_events"
    __table_args__ = (
        CheckConstraint("risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)", name="ck_risk_events_score_range"),
        Index("ix_risk_events_transaction_created_at", "transaction_id", "created_at"),
        Index("ix_risk_events_user_created_at", "user_id", "created_at"),
        Index("ix_risk_events_event_type", "event_type"),
    )

    transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    model_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("model_versions.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(100))
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))

    transaction: Mapped[Transaction | None] = relationship(back_populates="risk_events")
    user: Mapped[User | None] = relationship(back_populates="risk_events")
    model_version: Mapped[ModelVersion | None] = relationship(back_populates="risk_events")


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_event_created_at", "event_type", "created_at"),
        Index("ix_audit_logs_actor_created_at", "actor_user_id", "created_at"),
    )

    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(120))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
