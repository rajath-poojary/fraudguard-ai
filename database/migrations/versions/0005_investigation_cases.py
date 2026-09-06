"""Add investigation cases and investigator action history.

Revision ID: 0005_investigation_cases
Revises: 0004_data_foundation
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_investigation_cases"
down_revision: Union[str, Sequence[str], None] = "0004_data_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    op.create_table(
        "investigation_cases",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("alert_id", uuid_type, sa.ForeignKey("fraud_alerts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_to_id", uuid_type, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(30), server_default="OPEN", nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("resolution", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("alert_id", name="uq_investigation_cases_alert_id"),
    )
    op.create_index("ix_investigation_cases_status_created_at", "investigation_cases", ["status", "created_at"])
    op.create_table(
        "case_actions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("case_id", uuid_type, sa.ForeignKey("investigation_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action_type", sa.String(40), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_case_actions_case_created_at", "case_actions", ["case_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_case_actions_case_created_at", table_name="case_actions")
    op.drop_table("case_actions")
    op.drop_index("ix_investigation_cases_status_created_at", table_name="investigation_cases")
    op.drop_table("investigation_cases")