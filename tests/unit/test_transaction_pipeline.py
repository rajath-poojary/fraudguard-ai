"""Unit tests for the realistic transaction pipeline, historical behaviors,
8 fraud scenarios, and data leakage prevention.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from ml.data.pipeline import (
    LOCATIONS,
    SyntheticTransactionGenerator,
    haversine_distance_km,
)
from ml.data.splitting import TemporalSplitter


def test_schema_conformance():
    """Verify generated transactions conform to all 14 required foundation attributes."""
    generator = SyntheticTransactionGenerator(seed=123, duration_days=10)
    dataset = generator.generate_complete_dataset(num_users=15, num_merchants=8)
    assert len(dataset) > 0

    required_attributes = [
        "transaction_id",
        "user_id",
        "timestamp",
        "amount",
        "currency",
        "merchant_id",
        "merchant_category",
        "device_id",
        "ip_address",
        "location",
        "account_age",
        "payment_method",
        "transaction_status",
        "previous_transaction_id",
    ]

    for tx in dataset:
        for attr in required_attributes:
            assert hasattr(tx, attr), f"Missing required attribute: {attr}"
        assert isinstance(tx.transaction_id, UUID)
        assert isinstance(tx.user_id, UUID)
        assert isinstance(tx.timestamp, datetime)
        assert isinstance(tx.amount, Decimal)
        assert tx.amount > 0
        assert len(tx.currency) == 3
        assert isinstance(tx.merchant_id, UUID)
        assert isinstance(tx.merchant_category, str)
        assert isinstance(tx.device_id, UUID)
        assert isinstance(tx.ip_address, str)
        assert isinstance(tx.location, str)
        assert isinstance(tx.account_age, int)
        assert tx.account_age >= 0
        assert isinstance(tx.payment_method, str)
        assert tx.transaction_status in ("completed", "pending", "failed", "blocked")
        assert tx.previous_transaction_id is None or isinstance(tx.previous_transaction_id, UUID)


def test_generator_reproducibility():
    """Verify identical random seeds produce byte-identical transaction sequences."""
    gen1 = SyntheticTransactionGenerator(seed=999, duration_days=7)
    txs1 = gen1.generate_complete_dataset(num_users=10, num_merchants=5)

    gen2 = SyntheticTransactionGenerator(seed=999, duration_days=7)
    txs2 = gen2.generate_complete_dataset(num_users=10, num_merchants=5)

    assert len(txs1) == len(txs2)
    for t1, t2 in zip(txs1, txs2):
        assert t1.amount == t2.amount
        assert t1.timestamp == t2.timestamp
        assert t1.merchant_category == t2.merchant_category
        assert t1.ip_address == t2.ip_address
        assert t1.location == t2.location
        assert t1.is_fraud == t2.is_fraud
        assert t1.fraud_scenario == t2.fraud_scenario


def test_historical_user_consistency():
    """Verify legitimate user transactions adhere to their behavioral profile."""
    generator = SyntheticTransactionGenerator(seed=42, duration_days=20)
    generator.initialize_world(num_users=10, num_merchants=6)
    legit_stream = generator.generate_legitimate_stream(max_transactions_per_user=15)
    assert len(legit_stream) > 0

    user_map = {u.user_id: u for u in generator.users}

    for tx in legit_stream:
        user = user_map[tx.user_id]
        # Active diurnal hours adherence
        assert user.active_hours_start <= tx.timestamp.hour < user.active_hours_end

        # Amount range bounds
        assert float(tx.amount) >= user.min_amount * 0.95
        assert float(tx.amount) <= user.max_amount * 2.0

        # Location bounds (home location or registered travel locations)
        allowed_locations = {user.home_location, *user.travel_locations}
        assert tx.location in allowed_locations

        # Device bounds
        known_device_ids = {d.device_id for d in user.devices}
        assert tx.device_id in known_device_ids


def test_historical_previous_transaction_chaining():
    """Verify previous_transaction_id strictly chains transactions chronologically per user."""
    generator = SyntheticTransactionGenerator(seed=77, duration_days=15)
    dataset = generator.generate_complete_dataset(num_users=12, num_merchants=6)

    # Group by user and check sequential chaining
    user_txs: dict[UUID, list] = {}
    for tx in dataset:
        user_txs.setdefault(tx.user_id, []).append(tx)

    for user_id, tx_list in user_txs.items():
        assert len(tx_list) > 0
        # First transaction has no previous_transaction_id
        assert tx_list[0].previous_transaction_id is None
        # Subsequent transactions point directly to the preceding transaction id
        for i in range(1, len(tx_list)):
            assert tx_list[i].previous_transaction_id == tx_list[i - 1].transaction_id
            assert tx_list[i].timestamp >= tx_list[i - 1].timestamp


def test_fraud_scenario_1_account_takeover():
    generator = SyntheticTransactionGenerator(seed=101)
    generator.initialize_world(num_users=5, num_merchants=5)
    user = generator.users[0]
    known_device_ids = {d.device_id for d in user.devices}

    txs = generator.inject_account_takeover(user, datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc))
    assert len(txs) == 1
    tx = txs[0]
    assert tx.is_fraud is True
    assert tx.fraud_scenario == "account_takeover"
    assert tx.device_id not in known_device_ids
    assert tx.ip_address not in user.known_ips
    assert tx.location != user.home_location
    assert float(tx.amount) > user.typical_amount_mean * 5.0


def test_fraud_scenario_2_transaction_burst():
    generator = SyntheticTransactionGenerator(seed=102)
    generator.initialize_world(num_users=5, num_merchants=5)
    user = generator.users[0]

    txs = generator.inject_transaction_burst(user, datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc), burst_count=8)
    assert len(txs) == 8
    # Bursts must occur in rapid succession (< 10 minutes total for 8 transactions)
    duration_seconds = (txs[-1].timestamp - txs[0].timestamp).total_seconds()
    assert duration_seconds <= 600
    for tx in txs:
        assert tx.is_fraud is True
        assert tx.fraud_scenario == "transaction_burst"


def test_fraud_scenario_3_device_takeover():
    generator = SyntheticTransactionGenerator(seed=103)
    generator.initialize_world(num_users=5, num_merchants=5)
    user = generator.users[0]
    known_dev_ids = {d.device_id for d in user.devices}

    txs = generator.inject_device_takeover(user, datetime(2026, 1, 15, 16, 0, tzinfo=timezone.utc))
    assert len(txs) == 1
    assert txs[0].is_fraud is True
    assert txs[0].fraud_scenario == "device_takeover"
    assert txs[0].device_id not in known_dev_ids


def test_fraud_scenario_4_impossible_travel():
    generator = SyntheticTransactionGenerator(seed=104)
    generator.initialize_world(num_users=5, num_merchants=5)
    user = generator.users[0]

    txs = generator.inject_impossible_travel(user, datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc))
    assert len(txs) == 2
    tx1, tx2 = txs[0], txs[1]
    assert tx2.is_fraud is True
    assert tx2.fraud_scenario == "impossible_travel"

    delta_minutes = (tx2.timestamp - tx1.timestamp).total_seconds() / 60.0
    assert delta_minutes <= 30.0

    coord1 = LOCATIONS[tx1.location][:2]
    coord2 = LOCATIONS[tx2.location][:2]
    distance_km = haversine_distance_km(coord1, coord2)
    assert distance_km > 3000.0
    speed_kmh = (distance_km / delta_minutes) * 60.0
    assert speed_kmh > 1000.0


def test_fraud_scenario_5_merchant_abuse():
    generator = SyntheticTransactionGenerator(seed=105)
    generator.initialize_world(num_users=5, num_merchants=5)
    user = generator.users[0]

    txs = generator.inject_merchant_abuse(user, datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc))
    assert len(txs) == 3
    for tx in txs:
        assert tx.is_fraud is True
        assert tx.fraud_scenario == "merchant_abuse"
        assert tx.merchant_category in ("crypto", "luxury", "electronics")
        assert int(tx.amount) % 100 == 0  # Round dollar amounts


def test_fraud_scenario_6_card_testing():
    generator = SyntheticTransactionGenerator(seed=106)
    generator.initialize_world(num_users=5, num_merchants=5)
    user = generator.users[0]

    txs = generator.inject_card_testing(user, datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc), test_count=5)
    assert len(txs) == 5
    for tx in txs:
        assert tx.is_fraud is True
        assert tx.fraud_scenario == "card_testing"
        assert float(tx.amount) <= 5.00


def test_fraud_scenario_7_coordinated_fraud_network():
    generator = SyntheticTransactionGenerator(seed=107)
    generator.initialize_world(num_users=10, num_merchants=5)
    ring_users = generator.users[:4]

    txs = generator.inject_coordinated_fraud_network(ring_users, datetime(2026, 1, 20, 15, 0, tzinfo=timezone.utc))
    assert len(txs) == 4
    # All 4 separate user accounts share the exact same device and IP
    unique_users = {tx.user_id for tx in txs}
    unique_devices = {tx.device_id for tx in txs}
    unique_ips = {tx.ip_address for tx in txs}

    assert len(unique_users) == 4
    assert len(unique_devices) == 1
    assert len(unique_ips) == 1
    for tx in txs:
        assert tx.is_fraud is True
        assert tx.fraud_scenario == "coordinated_fraud_network"


def test_fraud_scenario_8_sudden_behavioral_change():
    generator = SyntheticTransactionGenerator(seed=108)
    generator.initialize_world(num_users=5, num_merchants=5)
    user = generator.users[0]

    txs = generator.inject_sudden_behavioral_change(user, datetime(2026, 1, 22, tzinfo=timezone.utc))
    assert len(txs) == 1
    tx = txs[0]
    assert tx.is_fraud is True
    assert tx.fraud_scenario == "sudden_behavioral_change"
    assert tx.timestamp.hour == 3  # Middle of the night
    assert float(tx.amount) >= user.typical_amount_mean * 10.0


def test_temporal_splitting_prevents_data_leakage():
    """Verify out-of-time train/val/test splitting guarantees zero temporal data leakage."""
    generator = SyntheticTransactionGenerator(seed=555, duration_days=60)
    dataset = generator.generate_complete_dataset(num_users=20, num_merchants=10)
    assert len(dataset) > 50

    splitter = TemporalSplitter(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
    splits = splitter.split(dataset)

    # Basic partitions exist and contain data
    assert len(splits.train) > 0
    assert len(splits.validation) > 0
    assert len(splits.test) > 0

    # Total counts match
    assert len(splits.train) + len(splits.validation) + len(splits.test) == len(dataset)

    # Absolute temporal boundaries verification
    train_max = max(tx.timestamp for tx in splits.train)
    val_min = min(tx.timestamp for tx in splits.validation)
    val_max = max(tx.timestamp for tx in splits.validation)
    test_min = min(tx.timestamp for tx in splits.test)

    assert train_max < val_min, f"Temporal train/val leakage! train_max={train_max}, val_min={val_min}"
    assert val_max < test_min, f"Temporal val/test leakage! val_max={val_max}, test_min={test_min}"
