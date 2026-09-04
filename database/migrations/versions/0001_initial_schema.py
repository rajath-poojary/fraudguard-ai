"""Create the initial FraudGuard PostgreSQL schema.

Revision ID: 0001_initial_schema
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    jsonb = postgresql.JSONB()

    op.create_table(
        "users",
        sa.Column("id", uuid, nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("length(trim(email)) > 3", name="ck_users_email_not_blank"),
    )
    op.create_index("ix_users_created_at", "users", ["created_at"])

    op.create_table(
        "merchants",
        sa.Column("id", uuid, nullable=False),
        sa.Column("external_id", sa.String(120), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("country_code", sa.String(2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name="uq_merchants_external_id"),
    )
    op.create_index("ix_merchants_name", "merchants", ["name"])

    op.create_table(
        "model_versions",
        sa.Column("id", uuid, nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("artifact_uri", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_name", "version", name="uq_model_versions_name_version"),
        sa.CheckConstraint("version > 0", name="ck_model_versions_version_positive"),
    )
    op.create_index("ix_model_versions_active", "model_versions", ["model_name", "is_active"])

    op.create_table(
        "devices",
        sa.Column("id", uuid, nullable=False),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("fingerprint", sa.String(255), nullable=False),
        sa.Column("platform", sa.String(50)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "fingerprint", name="uq_devices_user_fingerprint"),
    )
    op.create_index("ix_devices_fingerprint", "devices", ["fingerprint"])

    op.create_table(
        "transactions",
        sa.Column("id", uuid, nullable=False),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("merchant_id", uuid),
        sa.Column("device_id", uuid),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(30), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", jsonb),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("amount >= 0", name="ck_transactions_amount_non_negative"),
        sa.CheckConstraint("length(currency) = 3", name="ck_transactions_currency_iso"),
    )
    op.create_index("ix_transactions_user_created_at", "transactions", ["user_id", "created_at"])
    op.create_index("ix_transactions_merchant_created_at", "transactions", ["merchant_id", "created_at"])
    op.create_index("ix_transactions_device_created_at", "transactions", ["device_id", "created_at"])

    op.create_table(
        "fraud_alerts",
        sa.Column("id", uuid, nullable=False),
        sa.Column("transaction_id", uuid, nullable=False),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("risk_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(30), server_default=sa.text("'open'"), nullable=False),
        sa.Column("reason_code", sa.String(100), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id", name="uq_fraud_alerts_transaction_id"),
        sa.CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="ck_fraud_alerts_score_range"),
    )
    op.create_index("ix_fraud_alerts_status_created_at", "fraud_alerts", ["status", "created_at"])

    op.create_table(
        "risk_events",
        sa.Column("id", uuid, nullable=False),
        sa.Column("transaction_id", uuid),
        sa.Column("user_id", uuid),
        sa.Column("model_version_id", uuid),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("reason_code", sa.String(100)),
        sa.Column("risk_score", sa.Numeric(5, 2)),
        sa.Column("details", jsonb),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)", name="ck_risk_events_score_range"),
    )
    op.create_index("ix_risk_events_transaction_created_at", "risk_events", ["transaction_id", "created_at"])
    op.create_index("ix_risk_events_user_created_at", "risk_events", ["user_id", "created_at"])
    op.create_index("ix_risk_events_event_type", "risk_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("risk_events")
    op.drop_table("fraud_alerts")
    op.drop_table("transactions")
    op.drop_table("devices")
    op.drop_table("model_versions")
    op.drop_table("merchants")
    op.drop_table("users")
