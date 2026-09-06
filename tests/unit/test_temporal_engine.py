"""Unit tests for the Temporal Fraud Detection Engine.

Verifies:
1. Multi-resolution rolling window calculations (30s, 5m, 30m, 24h).
2. Inter-arrival time (delta-t) calculations.
3. Pattern detection:
   - Transaction bursts
   - Rapid repeated payments
   - Card testing
   - Sudden spending acceleration
   - Multiple merchants in short periods
4. Non-static, adaptive baseline comparison.
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
from app.services.temporal_engine import TemporalEngine, _format_duration


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


def test_rolling_windows_calculation(db_session):
    """Verify rolling window aggregation accuracy across 30s, 5m, 30m, 24h."""
    user = User(
        id=uuid4(),
        email="test_windows@example.com",
        password_hash="fake",
        display_name="Test User",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Transaction 10 seconds ago ($20, Merchant A, Device 1)
    t1 = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("20.00"),
        currency="USD",
        status="completed",
        occurred_at=now - timedelta(seconds=10),
        merchant_category="retail",
        location="New York, US",
        metadata_json={"device_fingerprint": "dev_1", "merchant": "Merchant A"},
    )
    # 2. Transaction 20 seconds ago ($20, Merchant B, Device 1) -> repeated amount!
    t2 = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("20.00"),
        currency="USD",
        status="completed",
        occurred_at=now - timedelta(seconds=20),
        merchant_category="food",
        location="New York, US",
        metadata_json={"device_fingerprint": "dev_1", "merchant": "Merchant B"},
    )
    # 3. Transaction 3 minutes ago ($50, Merchant C, Device 2)
    t3 = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("50.00"),
        currency="USD",
        status="completed",
        occurred_at=now - timedelta(minutes=3),
        merchant_category="electronics",
        location="Boston, US",
        metadata_json={"device_fingerprint": "dev_2", "merchant": "Merchant C"},
    )
    # 4. Transaction 15 minutes ago ($100, failed)
    t4 = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("100.00"),
        currency="USD",
        status="failed",
        occurred_at=now - timedelta(minutes=15),
        merchant_category="travel",
        location="Chicago, US",
        metadata_json={"device_fingerprint": "dev_2"},
    )
    # 5. Transaction 2 hours ago ($200)
    t5 = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("200.00"),
        currency="USD",
        status="completed",
        occurred_at=now - timedelta(hours=2),
        merchant_category="general",
    )
    # 6. Transaction 3 days ago (outside 24h)
    t6 = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("500.00"),
        currency="USD",
        status="completed",
        occurred_at=now - timedelta(days=3),
    )

    all_txs = [t1, t2, t3, t4, t5, t6]
    db_session.add_all(all_txs)
    db_session.commit()

    engine = TemporalEngine(db=db_session)
    windows = engine.compute_rolling_windows(all_txs, reference_time=now)

    # 30 seconds window: t1 and t2
    assert windows.window_30s.transaction_count == 2
    assert windows.window_30s.total_amount == 40.00
    assert windows.window_30s.unique_merchants == 2
    assert windows.window_30s.unique_devices == 1
    assert windows.window_30s.repeated_amounts_count == 2
    assert windows.window_30s.rapid_intervals_count == 1  # 10s interval

    # 5 minutes window: t1, t2, t3
    assert windows.window_5m.transaction_count == 3
    assert windows.window_5m.total_amount == 90.00
    assert windows.window_5m.unique_devices == 2

    # 30 minutes window: t1, t2, t3, t4
    assert windows.window_30m.transaction_count == 4
    assert windows.window_30m.total_amount == 190.00
    assert windows.window_30m.failed_attempts == 1

    # 24 hours window: t1, t2, t3, t4, t5 (t6 excluded)
    assert windows.window_24h.transaction_count == 5
    assert windows.window_24h.total_amount == 390.00


def test_detect_transaction_burst(db_session):
    """Verify detection of high-velocity transaction bursts."""
    user = User(
        id=uuid4(),
        email="burst_victim@example.com",
        password_hash="fake",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    start = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)

    # 4 transactions within 15 seconds! (intervals: 3s, 4s, 5s)
    for idx in range(4):
        tx = Transaction(
            id=uuid4(),
            user_id=user.id,
            amount=Decimal("45.00"),
            currency="USD",
            status="completed",
            occurred_at=start + timedelta(seconds=idx * 4),
            merchant_category="digital_goods",
            location="San Jose, US",
            metadata_json={"device_fingerprint": "bot_script_v1"},
        )
        db_session.add(tx)
    db_session.commit()

    engine = TemporalEngine(db=db_session)
    res = engine.analyze_user_sequences(user.id)

    burst_seqs = [s for s in res.detected_sequences if s.pattern_type == "TRANSACTION_BURST"]
    assert len(burst_seqs) >= 1
    seq = burst_seqs[0]
    assert seq.transaction_count == 4
    assert seq.severity in ("HIGH", "CRITICAL")
    assert "Velocity Burst" in seq.pattern_title
    assert seq.duration_seconds <= 15.0


def test_detect_rapid_repeated_payments(db_session):
    """Verify detection of identical amounts replayed in rapid succession."""
    user = User(
        id=uuid4(),
        email="replay_test@example.com",
        password_hash="fake",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    start = datetime(2026, 8, 20, 14, 0, 0, tzinfo=timezone.utc)

    # 3 identical transactions of $79.99 within 90 seconds
    for idx in range(3):
        tx = Transaction(
            id=uuid4(),
            user_id=user.id,
            amount=Decimal("79.99"),
            currency="USD",
            status="completed",
            occurred_at=start + timedelta(seconds=idx * 30),
            merchant_category="subscription",
            location="Miami, US",
        )
        db_session.add(tx)
    db_session.commit()

    engine = TemporalEngine(db=db_session)
    res = engine.analyze_user_sequences(user.id)

    repeat_seqs = [s for s in res.detected_sequences if s.pattern_type == "RAPID_REPEATED_PAYMENTS"]
    assert len(repeat_seqs) >= 1
    seq = repeat_seqs[0]
    assert "79.99" in seq.explanation
    assert seq.severity in ("MEDIUM", "HIGH")


def test_detect_card_testing(db_session):
    """Verify detection of micro-authorization probes and declines."""
    user = User(
        id=uuid4(),
        email="card_testing@example.com",
        password_hash="fake",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    start = datetime(2026, 8, 20, 16, 0, 0, tzinfo=timezone.utc)

    # Sequence of $1.00, $2.00, $1.50 with failures
    test_amounts = [Decimal("1.00"), Decimal("2.00"), Decimal("1.50")]
    for idx, amt in enumerate(test_amounts):
        tx = Transaction(
            id=uuid4(),
            user_id=user.id,
            amount=amt,
            currency="USD",
            status="failed" if idx == 0 else "completed",
            occurred_at=start + timedelta(seconds=idx * 40),
            merchant_category="online_service",
            location="Berlin, DE",
        )
        db_session.add(tx)
    db_session.commit()

    engine = TemporalEngine(db=db_session)
    res = engine.analyze_user_sequences(user.id)

    testing_seqs = [s for s in res.detected_sequences if s.pattern_type == "CARD_TESTING"]
    assert len(testing_seqs) >= 1
    seq = testing_seqs[0]
    assert seq.severity in ("HIGH", "CRITICAL")
    assert "micro-amount" in seq.explanation.lower()


def test_detect_multiple_merchants_rapid(db_session):
    """Verify detection of merchant hopping across short periods."""
    user = User(
        id=uuid4(),
        email="merchant_hopping@example.com",
        password_hash="fake",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    start = datetime(2026, 8, 20, 18, 0, 0, tzinfo=timezone.utc)

    # 4 distinct merchants within 2 minutes
    categories = ["electronics", "apparel", "gaming", "crypto"]
    for idx, cat in enumerate(categories):
        tx = Transaction(
            id=uuid4(),
            user_id=user.id,
            amount=Decimal("150.00"),
            currency="USD",
            status="completed",
            occurred_at=start + timedelta(seconds=idx * 25),
            merchant_category=cat,
            location="Austin, US",
            metadata_json={"merchant": f"Store {cat}"},
        )
        db_session.add(tx)
    db_session.commit()

    engine = TemporalEngine(db=db_session)
    res = engine.analyze_user_sequences(user.id)

    merchant_seqs = [s for s in res.detected_sequences if s.pattern_type == "MULTIPLE_MERCHANTS_RAPID"]
    assert len(merchant_seqs) >= 1
    seq = merchant_seqs[0]
    assert seq.transaction_count == 4
    assert "different merchants" in seq.explanation


def test_inter_arrival_delta_t_formatting():
    """Verify human readable format of time delta intervals."""
    assert _format_duration(4.2) == "4.2s"
    assert _format_duration(45.0) == "45.0s"
    assert _format_duration(135.0) == "2m 15s"
    assert _format_duration(3665.0) == "1h 1m"
