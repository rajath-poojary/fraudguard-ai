"""Add authentication and persisted transaction analysis fields.

Revision ID: 0002_analysis_auth
Revises: 0001_initial_schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_analysis_auth"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.alter_column("users", "password_hash", nullable=False)
    op.add_column("transactions", sa.Column("fraud_probability", sa.Numeric(5, 4)))
    op.add_column("transactions", sa.Column("anomaly_score", sa.Numeric(8, 5)))
    op.add_column("transactions", sa.Column("risk_score", sa.Numeric(5, 2)))
    op.add_column("transactions", sa.Column("risk_level", sa.String(10)))
    op.add_column("transactions", sa.Column("decision", sa.String(10)))
    op.add_column("transactions", sa.Column("reasons", postgresql.JSONB()))
    op.alter_column("fraud_alerts", "risk_score", type_=sa.Numeric(5, 2), existing_type=sa.Numeric(5, 4))
    op.alter_column("risk_events", "risk_score", type_=sa.Numeric(5, 2), existing_type=sa.Numeric(5, 4))
    op.create_check_constraint(
        "ck_transactions_risk_score_range",
        "transactions",
        "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)",
    )
    op.create_index("ix_transactions_decision_created_at", "transactions", ["decision", "created_at"])
    op.drop_constraint("ck_fraud_alerts_score_range", "fraud_alerts", type_="check")
    op.create_check_constraint(
        "ck_fraud_alerts_score_range", "fraud_alerts", "risk_score >= 0 AND risk_score <= 100"
    )
    op.drop_constraint("ck_risk_events_score_range", "risk_events", type_="check")
    op.create_check_constraint(
        "ck_risk_events_score_range",
        "risk_events",
        "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_risk_events_score_range", "risk_events", type_="check")
    op.create_check_constraint(
        "ck_risk_events_score_range",
        "risk_events",
        "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)",
    )
    op.drop_constraint("ck_fraud_alerts_score_range", "fraud_alerts", type_="check")
    op.create_check_constraint(
        "ck_fraud_alerts_score_range", "fraud_alerts", "risk_score >= 0 AND risk_score <= 1"
    )
    op.alter_column("fraud_alerts", "risk_score", type_=sa.Numeric(5, 4), existing_type=sa.Numeric(5, 2))
    op.alter_column("risk_events", "risk_score", type_=sa.Numeric(5, 4), existing_type=sa.Numeric(5, 2))
    op.drop_index("ix_transactions_decision_created_at", table_name="transactions")
    op.drop_constraint("ck_transactions_risk_score_range", "transactions", type_="check")
    for column in ("reasons", "decision", "risk_level", "risk_score", "anomaly_score", "fraud_probability"):
        op.drop_column("transactions", column)
    op.drop_column("users", "password_hash")
