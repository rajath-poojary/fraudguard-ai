"""Add canonical RBAC roles, audit logs, and detection policies.

Revision ID: 0007_rbac_audit_policies
Revises: 0006_investigation_feedback
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007_rbac_audit_policies"
down_revision: Union[str, Sequence[str], None] = "0006_investigation_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    constraints = {item["name"] for item in sa.inspect(bind).get_check_constraints("users")}
    if "ck_users_role" in constraints:
        op.drop_constraint("ck_users_role", "users", type_="check")
    op.execute("UPDATE users SET role = 'ADMIN' WHERE role = 'admin'")
    op.execute("UPDATE users SET role = 'INVESTIGATOR' WHERE role = 'user'")
    op.create_check_constraint("ck_users_role", "users", "role IN ('ADMIN', 'INVESTIGATOR', 'ANALYST')")

    uuid_type = postgresql.UUID(as_uuid=True)
    op.create_table(
        "detection_policies",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_by_id", uuid_type, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("name", name="uq_detection_policies_name"),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("actor_user_id", uuid_type, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resource_type", sa.String(60), nullable=False),
        sa.Column("resource_id", sa.String(120), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_audit_logs_event_created_at", "audit_logs", ["event_type", "created_at"])
    op.create_index("ix_audit_logs_actor_created_at", "audit_logs", ["actor_user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_actor_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_event_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("detection_policies")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'ADMIN'")
    op.execute("UPDATE users SET role = 'user' WHERE role IN ('INVESTIGATOR', 'ANALYST')")
    op.create_check_constraint("ck_users_role", "users", "role IN ('user', 'admin')")