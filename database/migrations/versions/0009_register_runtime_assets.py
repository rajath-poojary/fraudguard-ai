"""Register the trained model artifact and default detection policy.

Revision ID: 0009_register_runtime_assets
Revises: 0008_align_user_role_default
"""
from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0009_register_runtime_assets"
down_revision: Union[str, Sequence[str], None] = "0008_align_user_role_default"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    model_versions = sa.table(
        "model_versions",
        sa.column("id", sa.Uuid),
        sa.column("model_name", sa.String),
        sa.column("version", sa.Integer),
        sa.column("artifact_uri", sa.Text),
        sa.column("is_active", sa.Boolean),
        sa.column("trained_at", sa.DateTime(timezone=True)),
    )
    if not bind.execute(
        sa.select(model_versions.c.id).where(
            model_versions.c.model_name == "fraud-classifier",
            model_versions.c.version == 1,
        )
    ).first():
        bind.execute(model_versions.insert().values(
            id=uuid4(),
            model_name="fraud-classifier",
            version=1,
            artifact_uri="ml/models/fraud_model.joblib",
            is_active=True,
            trained_at=datetime.now(timezone.utc),
        ))

    policies = sa.table(
        "detection_policies",
        sa.column("id", sa.Uuid),
        sa.column("name", sa.String),
        sa.column("configuration", sa.JSON),
        sa.column("is_active", sa.Boolean),
    )
    if not bind.execute(sa.select(policies.c.id).where(policies.c.name == "risk-policy")).first():
        bind.execute(policies.insert().values(
            id=uuid4(),
            name="risk-policy",
            configuration={"source": "trained-model", "artifact_uri": "ml/models/fraud_model.joblib"},
            is_active=True,
        ))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM detection_policies WHERE name = 'risk-policy'"))
    bind.execute(sa.text("DELETE FROM model_versions WHERE model_name = 'fraud-classifier' AND version = 1"))