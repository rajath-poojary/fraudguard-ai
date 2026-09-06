import numpy as np
import pandas as pd
import pytest

from ml.anomaly_detection import IsolationForestAnomalyDetector, prepare_transaction_features


def make_transactions() -> pd.DataFrame:
    normal = pd.DataFrame(
        {
            "Time": np.arange(100, 130) * 60,
            "Amount": np.linspace(10, 40, 30),
            "feature_a": np.linspace(0.0, 1.0, 30),
            "Class": [0] * 30,
        }
    )
    unusual = pd.DataFrame(
        {
            "Time": [100000, 100060],
            "Amount": [10000.0, 15000.0],
            "feature_a": [100.0, 120.0],
            "Class": [1, 1],
        }
    )
    return pd.concat([normal, unusual], ignore_index=True)


def test_feature_preparation_excludes_supervised_label_and_adds_behavior_features():
    features = prepare_transaction_features(make_transactions())

    assert "Class" not in features
    assert {"hour", "day", "amount_log1p", "amount_missing"}.issubset(features.columns)


def test_detector_returns_scores_and_applies_configurable_threshold():
    transactions = make_transactions()
    detector = IsolationForestAnomalyDetector(
        contamination="auto", threshold=0.0, n_estimators=100, random_state=7
    ).fit(transactions)

    result = detector.predict_anomalies(transactions)

    assert list(result["anomaly_score"].index) == list(transactions.index)
    assert result["anomaly_score"].notna().all()
    assert result["is_anomaly"].equals(result["anomaly_score"] >= 0.0)
    assert result.iloc[-2:]["anomaly_score"].mean() > result.iloc[:30]["anomaly_score"].mean()
    assert detector.fit_on_legitimate_only_ is True
    assert detector.training_rows_ == 30
    assert result.iloc[-1]["top_anomaly_features"]

    detector.threshold = 1.0
    assert not detector.predict_anomalies(transactions)["is_anomaly"].any()


def test_detector_handles_missing_numeric_values():
    transactions = make_transactions()
    transactions.loc[0, "Amount"] = np.nan

    result = IsolationForestAnomalyDetector(n_estimators=50, random_state=1).fit(transactions).predict_anomalies(transactions)

    assert result["anomaly_score"].notna().all()


def test_detector_rejects_non_numeric_transactions():
    with pytest.raises(ValueError, match="numeric behavior features"):
        prepare_transaction_features(pd.DataFrame({"merchant": ["a", "b"]}))
