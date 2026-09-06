"""Add transaction data foundation fields.

Revision ID: 0004_data_foundation
Revises: 0003_user_roles
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_data_foundation"
down_revision: Union[str, Sequence[str], None] = "0003_user_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)

    op.add_column("transactions", sa.Column("merchant_category", sa.String(100), nullable=True))
    op.add_column("transactions", sa.Column("ip_address", sa.String(45), nullable=True))
    op.add_column("transactions", sa.Column("location", sa.String(100), nullable=True))
    op.add_column("transactions", sa.Column("account_age", sa.Integer(), nullable=True))
    op.add_column("transactions", sa.Column("payment_method", sa.String(50), nullable=True))
    op.add_column("transactions", sa.Column("previous_transaction_id", uuid_type, nullable=True))
    op.add_column("transactions", sa.Column("is_fraud", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("transactions", sa.Column("fraud_scenario", sa.String(50), nullable=True))

    op.create_foreign_key(
        "fk_transactions_previous_transaction_id",
        "transactions",
        "transactions",
        ["previous_transaction_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_transactions_ip_address_created_at", "transactions", ["ip_address", "created_at"])
    op.create_index("ix_transactions_previous_tx_id", "transactions", ["previous_transaction_id"])
    op.create_index("ix_transactions_is_fraud", "transactions", ["is_fraud"])


def downgrade() -> None:
    op.drop_index("ix_transactions_is_fraud", table_name="transactions")
    op.drop_index("ix_transactions_previous_tx_id", table_name="transactions")
    op.drop_index("ix_transactions_ip_address_created_at", table_name="transactions")
    op.drop_constraint("fk_transactions_previous_transaction_id", "transactions", type_="foreignkey")

    for col in (
        "fraud_scenario",
        "is_fraud",
        "previous_transaction_id",
        "payment_method",
        "account_age",
        "location",
        "ip_address",
        "merchant_category",
    ):
        op.drop_column("transactions", col)
