"""Unit tests for the Behavioral Intelligence Engine.

Verifies:
1. Strict lookahead-free baseline calculation (current transaction excluded).
2. Accurate statistical baselines (mean, median, standard deviation, distributions).
3. 16 behavioral features & multi-dimensional deviation scoring.
4. Edge cases (insufficient history, zero variance, new device/IP).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import Transaction, User
from app.services.behavior_engine import BehaviorEngine


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


def test_lookahead_free_baseline_exclusion(db_session):
    """Verify that current transaction is NEVER part of its own baseline calculation."""
    user = User(
        id=uuid4(),
        email="test_user@example.com",
        password_hash="fakehash",
        display_name="Test User",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    base_time = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Add 6 historical transactions of $50 each
    history_txs = []
    for i in range(6):
        tx = Transaction(
            id=uuid4(),
            user_id=user.id,
            amount=Decimal("50.00"),
            currency="USD",
            status="completed",
            occurred_at=base_time + timedelta(days=i),
            merchant_category="grocery",
            location="New York, US",
            ip_address="192.168.1.50",
            metadata_json={"device_fingerprint": "dev_phone_1"},
            is_fraud=False,
        )
        history_txs.append(tx)
        db_session.add(tx)

    # Current transaction: huge outlier of $5,000
    current_tx = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("5000.00"),
        currency="USD",
        status="completed",
        occurred_at=base_time + timedelta(days=10),
        merchant_category="electronics",
        location="Tokyo, JP",
        ip_address="10.0.0.99",
        metadata_json={"device_fingerprint": "dev_hacker_99"},
        is_fraud=True,
    )
    db_session.add(current_tx)
    db_session.commit()

    engine = BehaviorEngine(db=db_session)
    profile = engine.get_user_behavior_profile(user_id=user.id, current_transaction_id=current_tx.id)

    # If contaminated, average would be > $700. If uncontaminated, average is exactly $50.00
    baseline = profile.behavioral_baseline
    assert baseline.historical_transaction_count == 6
    assert baseline.average_transaction_amount == 50.00
    assert baseline.median_transaction_amount == 50.00
    assert baseline.standard_deviation == 0.00

    # Current activity reflects the evaluated transaction
    curr = profile.current_activity
    assert curr is not None
    assert curr.transaction_id == current_tx.id
    assert curr.amount == 5000.00

    # Deviation analysis detected huge anomalies
    dev = profile.current_deviation
    assert dev is not None
    assert dev.composite_deviation_score > 0.5
    assert dev.overall_risk_level == "HIGH"

    # Novelty checks triggered
    assert dev.device_novelty.score == 1.0
    assert dev.location_deviation.score > 0.8
    assert dev.ip_novelty.score > 0.8


def test_behavioral_features_calculation(db_session):
    """Verify calculation of all 16 specified behavioral features."""
    user = User(
        id=uuid4(),
        email="shopper@example.com",
        password_hash="fakehash",
        display_name="Shopper",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    start = datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)
    amounts = [20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0]

    for idx, amt in enumerate(amounts):
        # Even indices at 10:00, odd at 14:00
        hour = 10 if idx % 2 == 0 else 14
        tx = Transaction(
            id=uuid4(),
            user_id=user.id,
            amount=Decimal(str(amt)),
            currency="USD",
            status="completed" if idx < 7 else "failed",
            occurred_at=start + timedelta(days=idx, hours=hour - 10),
            merchant_category="retail" if idx % 2 == 0 else "dining",
            location="San Francisco, US",
            ip_address="172.16.0.10",
            metadata_json={"device_fingerprint": "macbook_pro_1"},
            is_fraud=(idx == 6),  # 1 historical fraud
        )
        db_session.add(tx)
    db_session.commit()

    # Create current normal transaction
    curr = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("55.00"),
        currency="USD",
        status="completed",
        occurred_at=start + timedelta(days=12),
        merchant_category="retail",
        location="San Francisco, US",
        ip_address="172.16.0.10",
        metadata_json={"device_fingerprint": "macbook_pro_1"},
        is_fraud=False,
    )
    db_session.add(curr)
    db_session.commit()

    engine = BehaviorEngine(db=db_session)
    profile = engine.get_user_behavior_profile(user.id, current_transaction_id=curr.id)
    baseline = profile.behavioral_baseline

    # Check baseline stats
    assert baseline.historical_transaction_count == 8
    assert baseline.has_sufficient_history is True
    assert baseline.average_transaction_amount == 55.00
    assert baseline.median_transaction_amount == 55.00
    assert baseline.failed_transaction_count == 1
    assert baseline.historical_fraud_association == 1
    assert baseline.min_transaction_amount == 20.00
    assert baseline.max_transaction_amount == 90.00
    assert "macbook_pro_1" in baseline.known_devices
    assert "172.16.0.10" in baseline.known_ip_addresses

    # Current transaction is normal: amount = $55 (mean = $55) -> z-score = 0
    dev = profile.current_deviation
    assert dev.amount_deviation.level == "normal"
    assert dev.device_novelty.score == 0.0
    assert dev.ip_novelty.score == 0.0
    assert dev.location_deviation.level == "normal"
    assert dev.composite_deviation_score < 0.35
    assert dev.overall_risk_level == "LOW"


def test_insufficient_history_safeguard(db_session):
    """Ensure users with fewer than 5 transactions do not receive misleading outlier scores."""
    user = User(
        id=uuid4(),
        email="newuser@example.com",
        password_hash="fakehash",
        display_name="New User",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    # User has only 1 prior transaction
    t1 = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("25.00"),
        currency="USD",
        status="completed",
        occurred_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(t1)

    t2 = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("150.00"),
        currency="USD",
        status="completed",
        occurred_at=datetime(2026, 8, 2, 10, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(t2)
    db_session.commit()

    engine = BehaviorEngine(db=db_session, min_history_threshold=5)
    profile = engine.get_user_behavior_profile(user.id, current_transaction_id=t2.id)

    baseline = profile.behavioral_baseline
    assert baseline.historical_transaction_count == 1
    assert baseline.has_sufficient_history is False

    dev = profile.current_deviation
    assert dev.amount_deviation.level == "insufficient_history"
    assert dev.transaction_frequency_deviation.level == "insufficient_history"
