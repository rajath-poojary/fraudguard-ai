"""API Integration tests for Temporal Fraud Detection Endpoints."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base, Transaction, User


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session: Session):
    """FastAPI test client with database dependency overridden."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_temporal_sequences_api_endpoints(client: TestClient, db_session: Session):
    """Verify GET /temporal/sequences and user analysis responses."""
    user = User(
        id=uuid4(),
        email="temporal_analyst@example.com",
        password_hash=hash_password("pw123"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    base_time = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    # Add burst transactions
    tx_ids = []
    for i in range(4):
        t = Transaction(
            id=uuid4(),
            user_id=user.id,
            amount=Decimal("30.00"),
            currency="USD",
            status="completed",
            occurred_at=base_time + timedelta(seconds=i * 5),
            merchant_category="digital",
            location="Seattle, US",
            metadata_json={"device_fingerprint": "macbook_pro_16"},
        )
        tx_ids.append(t.id)
        db_session.add(t)
    db_session.commit()

    token = create_access_token(user_id=user.id, role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Test GET /temporal/sequences
    resp = client.get("/temporal/sequences", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "patterns_summary" in data
    assert data["total"] >= 1

    seq = data["items"][0]
    assert "sequence_id" in seq
    assert "pattern_type" in seq
    assert "duration_formatted" in seq
    assert len(seq["events"]) >= 2
    # Verify delta-t is present on events
    assert "time_since_previous_formatted" in seq["events"][1]

    # 2. Test GET /temporal/users/{id}/analysis
    resp_user = client.get(f"/temporal/users/{user.id}/analysis", headers=headers)
    assert resp_user.status_code == 200
    user_data = resp_user.json()
    assert user_data["user_id"] == str(user.id)
    assert "current_rolling_windows" in user_data
    assert "window_30s" in user_data["current_rolling_windows"]
    assert "full_event_timeline" in user_data

    # 3. Test GET /temporal/transactions/{id}/context
    target_tx_id = tx_ids[2]
    resp_tx = client.get(f"/temporal/transactions/{target_tx_id}/context", headers=headers)
    assert resp_tx.status_code == 200
    tx_data = resp_tx.json()
    assert tx_data["transaction_id"] == str(target_tx_id)
    assert "rolling_windows" in tx_data
    assert "preceding_events" in tx_data
    assert len(tx_data["preceding_events"]) == 2
