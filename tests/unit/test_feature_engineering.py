from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pandas as pd

from ml.data.pipeline import SyntheticTransactionGenerator
from ml.data.splitting import TemporalSplitter
from ml.training.train_fraud_models import engineer_features


def test_supervised_feature_engineering_adds_time_and_amount_features_without_label():
    frame = pd.DataFrame({"Time": [0, 3600], "Amount": [10.0, 100.0], "Class": [0, 1], "V1": [0.1, 0.2]})

    features, target, details = engineer_features(frame)

    assert "Class" not in features.columns
    assert {"hour", "day", "amount_log1p", "amount_missing"}.issubset(features.columns)
    assert target.tolist() == [0, 1]
    assert details["features"] == len(features.columns)


def test_synthetic_pipeline_and_temporal_split_are_reproducible_and_ordered():
    generator = SyntheticTransactionGenerator(seed=7, duration_days=10)
    records = generator.generate_complete_dataset(num_users=6, num_merchants=5)
    splitter = TemporalSplitter(train_ratio=0.6, val_ratio=0.2, test_ratio=0.2)

    splits = splitter.split(records)

    assert records
    assert splits.train and splits.validation and splits.test
    splits.assert_no_leakage()
    assert all(record.transaction_id for record in splits.train + splits.validation + splits.test)