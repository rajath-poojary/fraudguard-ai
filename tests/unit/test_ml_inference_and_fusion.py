from types import SimpleNamespace

import pandas as pd

from app.services.risk_engine import DecisionPolicy, RiskEngine, RiskSignals


class StubClassifier:
    def predict_proba(self, features):
        return [[0.12, 0.88]]


class StubAnomalyDetector:
    def anomaly_score(self, features):
        return pd.Series([0.91])


def test_model_probability_and_anomaly_are_fused_into_explainable_decision():
    engine = RiskEngine(StubClassifier(), StubAnomalyDetector(), policy=DecisionPolicy(block_probability=0.8))

    assessment = engine.assess_with_features(
        {"amount": 2500, "transaction_frequency": 7},
        pd.DataFrame([[1.0]]),
        RiskSignals(0.0, 0.0, 0.4, 7, 0.8, 0.0, 0.0, temporal_evidence=0.9, behavior_deviation=0.7),
    )

    assert assessment.fraud_probability == 0.88
    assert assessment.decision == "BLOCK"
    assert assessment.risk_score >= assessment.fraud_probability * 100
    assert "TEMPORAL_VELOCITY" in assessment.reason_codes
    assert assessment.explanation["expected_loss"] == 2200.0


def test_low_probability_with_supporting_evidence_does_not_override_probability_primary_policy():
    engine = RiskEngine(policy=DecisionPolicy(review_probability=0.6, block_probability=0.9))

    assessment = engine.score(
        RiskSignals(0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, network_evidence=1.0),
        {"amount": 20},
    )

    assert assessment.fraud_probability == 0.2
    assert assessment.decision == "REVIEW"
    assert assessment.risk_score < 50