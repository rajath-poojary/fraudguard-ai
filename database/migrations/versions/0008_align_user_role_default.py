"""Align the users role default with canonical RBAC roles.

Revision ID: 0008_align_user_role_default
Revises: 0007_rbac_audit_policies
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_align_user_role_default"
down_revision: Union[str, Sequence[str], None] = "0007_rbac_audit_policies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(length=20),
        server_default=sa.text("'INVESTIGATOR'"),
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(length=20),
        server_default=sa.text("'user'"),
    )
