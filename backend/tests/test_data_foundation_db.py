"""Integration tests for the transaction data foundation in the database and dashboard.

Verifies:
1. Database persistence of all 14 schema attributes and self-referential chaining.
2. 100% dynamic database-backed dashboard statistics (no hardcoded metrics).
3. Synthetic seeder database population.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base, Device, FraudAlert, Merchant, RiskEvent, Transaction, User
from database.seeds.seed_transactions import seed_database


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database session with multi-dialect support."""
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


def test_transaction_foundation_columns_and_chaining(db_session: Session):
    """Verify transaction foundation fields persist and self-referential chaining works."""
    user = User(
        id=uuid4(),
        email="testuser@example.com",
        password_hash=hash_password("Pass123!"),
        role="user",
        is_active=True,
    )
    merchant = Merchant(
        id=uuid4(),
        external_id="merch_test_01",
        name="Apex Gadgets",
        category="electronics",
        country_code="US",
    )
    device = Device(
        id=uuid4(),
        user_id=user.id,
        fingerprint="fp-device-abc",
        platform="iOS",
    )
    db_session.add_all([user, merchant, device])
    db_session.commit()

    # Create transaction 1 (legitimate historical transaction)
    tx1 = Transaction(
        id=uuid4(),
        user_id=user.id,
        merchant_id=merchant.id,
        device_id=device.id,
        amount=Decimal("150.00"),
        currency="USD",
        status="completed",
        occurred_at=datetime(2026, 1, 10, 14, 30, tzinfo=timezone.utc),
        merchant_category="electronics",
        ip_address="198.51.100.12",
        location="San Francisco, US",
        account_age=60,
        payment_method="credit_card",
        previous_transaction_id=None,
        is_fraud=False,
        fraud_scenario=None,
        risk_score=Decimal("12.50"),
        risk_level="LOW",
        decision="APPROVE",
    )
    db_session.add(tx1)
    db_session.commit()

    # Create transaction 2 (chained to transaction 1 with fraud scenario)
    tx2 = Transaction(
        id=uuid4(),
        user_id=user.id,
        merchant_id=merchant.id,
        device_id=device.id,
        amount=Decimal("950.00"),
        currency="USD",
        status="blocked",
        occurred_at=datetime(2026, 1, 10, 14, 50, tzinfo=timezone.utc),
        merchant_category="electronics",
        ip_address="203.0.113.88",
        location="Tokyo, JP",
        account_age=60,
        payment_method="credit_card",
        previous_transaction_id=tx1.id,
        is_fraud=True,
        fraud_scenario="impossible_travel",
        risk_score=Decimal("94.00"),
        risk_level="HIGH",
        decision="BLOCK",
    )
    db_session.add(tx2)
    db_session.commit()

    # Query back tx2 and verify all schema fields and relationship
    loaded = db_session.get(Transaction, tx2.id)
    assert loaded is not None
    assert loaded.transaction_id == tx2.id
    assert loaded.timestamp == tx2.occurred_at
    assert loaded.transaction_status == "blocked"
    assert loaded.merchant_category == "electronics"
    assert loaded.ip_address == "203.0.113.88"
    assert loaded.location == "Tokyo, JP"
    assert loaded.account_age == 60
    assert loaded.payment_method == "credit_card"
    assert loaded.is_fraud is True
    assert loaded.fraud_scenario == "impossible_travel"
    assert loaded.previous_transaction_id == tx1.id
    assert loaded.previous_transaction is not None
    assert loaded.previous_transaction.id == tx1.id
    assert loaded.previous_transaction.amount == Decimal("150.00")


def test_dashboard_statistics_dynamically_originates_from_database(db_session: Session, client: TestClient):
    """Verify all dashboard statistics are computed directly from the database (no hardcoding)."""
    admin_user = User(
        id=uuid4(),
        email="admin@example.com",
        password_hash=hash_password("AdminPass123!"),
        role="admin",
        is_active=True,
    )
    merchant = Merchant(
        id=uuid4(),
        external_id="merch_dash_01",
        name="Crypto Vault Exchange",
        category="crypto",
        country_code="US",
    )
    device = Device(
        id=uuid4(),
        user_id=admin_user.id,
        fingerprint="fp-dash-device",
        platform="macOS",
    )
    db_session.add_all([admin_user, merchant, device])
    db_session.commit()

    token = create_access_token(admin_user.id, role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    # Initially zero transactions
    resp0 = client.get("/dashboard/statistics", headers=headers)
    assert resp0.status_code == 200
    data0 = resp0.json()
    assert data0["total_transactions"] == 0
    assert data0["total_volume"] == 0.0
    assert data0["exposure_prevented"] == 0.0
    assert data0["blocked_transactions"] == 0
    assert data0["fraud_rate"] == 0.0

    # Insert 1 legitimate transaction ($200.00) and 1 blocked fraud transaction ($1,800.00)
    tx_legit = Transaction(
        id=uuid4(),
        user_id=admin_user.id,
        merchant_id=merchant.id,
        device_id=device.id,
        amount=Decimal("200.00"),
        currency="USD",
        status="completed",
        occurred_at=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
        risk_score=Decimal("10.00"),
        risk_level="LOW",
        decision="APPROVE",
        is_fraud=False,
    )
    tx_fraud = Transaction(
        id=uuid4(),
        user_id=admin_user.id,
        merchant_id=merchant.id,
        device_id=device.id,
        amount=Decimal("1800.00"),
        currency="USD",
        status="blocked",
        occurred_at=datetime(2026, 2, 1, 11, 0, tzinfo=timezone.utc),
        risk_score=Decimal("95.00"),
        risk_level="HIGH",
        decision="BLOCK",
        is_fraud=True,
        fraud_scenario="account_takeover",
    )
    alert = FraudAlert(
        id=uuid4(),
        transaction_id=tx_fraud.id,
        user_id=admin_user.id,
        risk_score=Decimal("95.00"),
        status="open",
        reason_code="ALERT_ACCOUNT_TAKEOVER",
    )
    db_session.add_all([tx_legit, tx_fraud, alert])
    db_session.commit()

    # Query dashboard endpoint again: numbers MUST dynamically match the DB additions
    resp1 = client.get("/dashboard/statistics", headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()

    assert data1["total_transactions"] == 2
    assert data1["total_volume"] == 2000.0
    assert data1["exposure_prevented"] == 1800.0
    assert data1["blocked_transactions"] == 1
    assert data1["approved_transactions"] == 1
    assert data1["total_alerts"] == 1
    assert data1["active_investigations"] == 1
    assert data1["fraud_rate"] == 50.0  # 1 blocked out of 2 total = 50%
    assert data1["risk_distribution"]["LOW"] == 1
    assert data1["risk_distribution"]["HIGH"] == 1

    # Top risky merchants and devices must originate from database joins
    assert len(data1["top_risky_merchants"]) == 1
    assert data1["top_risky_merchants"][0]["name"] == "Crypto Vault Exchange"
    assert data1["top_risky_merchants"][0]["fraud_transactions"] == 1

    assert len(data1["top_risky_devices"]) == 1
    assert data1["top_risky_devices"][0]["fingerprint"] == "fp-dash-device"
    assert data1["top_risky_devices"][0]["fraud_transactions"] == 1

    # Trend series must have the aggregate for 2026-02-01
    assert len(data1["fraud_trend"]) >= 1
    trend_entry = data1["fraud_trend"][0]
    assert trend_entry["transactions"] == 2
    assert trend_entry["fraud_count"] == 1
    assert trend_entry["volume"] == 2000.0


def test_database_seeder_pipeline_execution(db_session: Session):
    """Verify seed_database creates world entities, historical transaction chains, and alerts."""
    summary = seed_database(
        db_session,
        seed=123,
        num_users=6,
        num_merchants=5,
        duration_days=5,
        default_password="TestSeedPassword123!",
    )

    assert summary["users"] >= 6
    assert summary["merchants"] >= 5
    assert summary["transactions"] > 0
    assert summary["fraud_alerts"] > 0
    assert summary["risk_events"] > 0

    # Verify admin and demo users were created
    admin = db_session.scalar(select(User).where(User.email == "admin@fraudguard.local"))
    assert admin is not None
    demo = db_session.scalar(select(User).where(User.email == "demo@fraudguard.local"))
    assert demo is not None

    # Check that fraudulent transactions have fraud_scenario set
    fraud_txs = list(db_session.scalars(select(Transaction).where(Transaction.is_fraud == True)))
    assert len(fraud_txs) > 0
    for f_tx in fraud_txs:
        assert f_tx.fraud_scenario is not None
        assert f_tx.status == "blocked"
