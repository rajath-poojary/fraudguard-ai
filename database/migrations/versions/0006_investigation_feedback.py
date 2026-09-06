"""Add immutable investigator feedback snapshots.

Revision ID: 0006_investigation_feedback
Revises: 0005_investigation_cases
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006_investigation_feedback"
down_revision: Union[str, Sequence[str], None] = "0005_investigation_cases"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    op.create_table(
        "investigation_feedback",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("case_id", uuid_type, sa.ForeignKey("investigation_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_id", uuid_type, sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("label", sa.String(30), nullable=False),
        sa.Column("fraud_probability", sa.Numeric(8, 6), nullable=True),
        sa.Column("risk_score", sa.Numeric(8, 2), nullable=True),
        sa.Column("reason_codes", sa.JSON(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_investigation_feedback_case_created_at", "investigation_feedback", ["case_id", "created_at"])
    op.create_index("ix_investigation_feedback_label_created_at", "investigation_feedback", ["label", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_investigation_feedback_label_created_at", table_name="investigation_feedback")
    op.drop_index("ix_investigation_feedback_case_created_at", table_name="investigation_feedback")
    op.drop_table("investigation_feedback")