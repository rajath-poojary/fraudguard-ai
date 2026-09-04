"""Add role-based authorization to users.

Revision ID: 0003_user_roles
Revises: 0002_transaction_analysis_and_auth
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_user_roles"
down_revision: Union[str, Sequence[str], None] = "0002_analysis_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    if "role" not in columns:
        op.add_column("users", sa.Column("role", sa.String(20), server_default=sa.text("'user'"), nullable=False))
    constraints = {
        constraint["name"] for constraint in sa.inspect(bind).get_check_constraints("users")
    }
    if "ck_users_role" not in constraints:
        op.create_check_constraint("ck_users_role", "users", "role IN ('user', 'admin')")


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")