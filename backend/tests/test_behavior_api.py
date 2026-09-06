"""API integration tests for behavioral intelligence endpoints.

Verifies:
1. GET /users/{id}/behavior-profile returns full behavioral baseline, current deviation, risk indicators, recent activity, and timeline.
2. Access control:
   - Admin can query any user's profile.
   - User can query their own profile.
   - User is forbidden (403) from querying another user's profile.
"""

from datetime import datetime, timezone
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


def test_get_behavior_profile_endpoint(client: TestClient, db_session: Session):
    """Verify GET /users/{id}/behavior-profile returns expected schema."""
    user = User(
        id=uuid4(),
        email="operator@example.com",
        password_hash=hash_password("password123"),
        display_name="Operator User",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    # Add 5 transactions
    base_time = datetime(2026, 8, 1, 14, 30, 0, tzinfo=timezone.utc)
    for i in range(5):
        tx = Transaction(
            id=uuid4(),
            user_id=user.id,
            amount=Decimal("120.00"),
            currency="USD",
            status="completed",
            occurred_at=base_time,
            merchant_category="travel",
            location="London, UK",
            ip_address="82.165.197.1",
            metadata_json={"device_fingerprint": "iphone_15_pro"},
        )
        db_session.add(tx)
    db_session.commit()

    token = create_access_token(user_id=user.id, role="user")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(f"/users/{user.id}/behavior-profile", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["user_id"] == str(user.id)
    assert data["user_email"] == "operator@example.com"
    assert "behavioral_baseline" in data
    assert "current_deviation" in data
    assert "risk_indicators" in data
    assert "recent_activity" in data
    assert "behavior_timeline" in data

    baseline = data["behavioral_baseline"]
    assert baseline["historical_transaction_count"] == 4  # 5 total - 1 (current excluded)
    assert baseline["average_transaction_amount"] == 120.00


def test_access_control_on_behavior_profile(client: TestClient, db_session: Session):
    """Regular user cannot access another user's profile; admin can access any."""
    user_a = User(
        id=uuid4(),
        email="usera@example.com",
        password_hash=hash_password("pw"),
        role="user",
        is_active=True,
    )
    user_b = User(
        id=uuid4(),
        email="userb@example.com",
        password_hash=hash_password("pw"),
        role="user",
        is_active=True,
    )
    admin = User(
        id=uuid4(),
        email="admin@example.com",
        password_hash=hash_password("pw"),
        role="admin",
        is_active=True,
    )
    db_session.add_all([user_a, user_b, admin])
    db_session.commit()

    token_user_a = create_access_token(user_id=user_a.id, role="user")
    token_admin = create_access_token(user_id=admin.id, role="admin")

    # User A tries to access User B -> 403 Forbidden
    resp = client.get(
        f"/users/{user_b.id}/behavior-profile",
        headers={"Authorization": f"Bearer {token_user_a}"},
    )
    assert resp.status_code == 403

    # Admin accesses User B -> 200 OK
    resp = client.get(
        f"/users/{user_b.id}/behavior-profile",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert resp.status_code == 200
