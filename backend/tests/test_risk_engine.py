import math

import pytest

from app.services.risk_engine import RiskAssessment, RiskEngine, RiskSignals, RuleEngine, RuleMatch


def high_amount_rule(transaction: dict[str, object]) -> RuleMatch | None:
    if float(transaction.get("amount", 0)) > 1000:
        return RuleMatch("HIGH_AMOUNT", "Transaction exceeds configured amount limit")
    return None


def test_normal_transaction_is_low_and_approved():
    assessment = RiskEngine().score(
        RiskSignals(0.02, 0.0, 0.0, 1, 0.0, 0.0, 0.0)
    )

    assert isinstance(assessment, RiskAssessment)
    assert assessment.risk_score == pytest.approx(1.6, abs=0.001)
    assert assessment.risk_level == "LOW"
    assert assessment.decision == "APPROVE"
    assert assessment.reasons


def test_suspicious_transaction_is_medium_and_reviewed():
    assessment = RiskEngine().score(
        RiskSignals(0.7, 0.8, 0.7, 5, 0.4, 0.6, 0.5),
        {"amount": 2000},
    )

    assert assessment.risk_score == pytest.approx(66.5, abs=0.001)
    assert assessment.risk_level == "MEDIUM"
    assert assessment.decision == "REVIEW"
    assert "ML_FRAUD_PROBABILITY" in assessment.reason_codes
    assert len(assessment.reasons) >= 1


def test_high_risk_transaction_is_blocked_with_rule_reason():
    assessment = RiskEngine(rule_engine=RuleEngine((high_amount_rule,))).score(
        RiskSignals(1.0, 1.0, 1.0, 50, 1.0, 1.0, 1.0),
        {"amount": 5000},
    )

    assert assessment.risk_score == pytest.approx(100.0)
    assert assessment.risk_level == "HIGH"
    assert assessment.decision == "BLOCK"
    assert assessment.reason_codes[-1] == "HIGH_AMOUNT"
    assert any("amount limit" in reason for reason in assessment.reasons)


def test_edge_cases_are_validated_and_thresholds_are_configurable():
    low_boundary = RiskEngine(medium_threshold=20, high_threshold=80).score(
        RiskSignals(0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0)
    )
    assert low_boundary.risk_score == 0
    assert low_boundary.decision == "APPROVE"
    assert low_boundary.reasons

    with pytest.raises(ValueError, match="between 0 and 1"):
        RiskEngine().score(RiskSignals(1.1, 0, 0, 0, 0, 0, 0))
    with pytest.raises(ValueError, match="cannot be negative"):
        RiskEngine().score(RiskSignals(0, 0, 0, -1, 0, 0, 0))
    with pytest.raises(ValueError, match="finite"):
        RiskEngine().score(RiskSignals(math.nan, 0, 0, 0, 0, 0, 0))
    with pytest.raises(ValueError, match="thresholds"):
        RiskEngine(medium_threshold=90, high_threshold=80)
