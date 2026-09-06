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
        CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
        Index("ix_users_created_at", "created_at"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    devices: Mapped[list["Device"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
    fraud_alerts: Mapped[list["FraudAlert"]] = relationship(back_populates="user")
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="user")


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
