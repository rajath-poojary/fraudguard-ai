from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID


class Base(DeclarativeBase):
    metadata = MetaData()


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc)
    )
