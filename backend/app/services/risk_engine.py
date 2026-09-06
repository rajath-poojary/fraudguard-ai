"""Modular FraudGuard risk scoring and signal orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Callable, Mapping, Protocol


class FraudClassifier(Protocol):
    def predict_proba(self, features: Any) -> Any:
        """Return class probabilities with fraud as column one."""


class AnomalyDetector(Protocol):
    def anomaly_score(self, transactions: Any) -> Any:
        """Return a higher-is-more-anomalous score."""


@dataclass(frozen=True)
class RiskSignals:
    """Normalized risk inputs, except transaction frequency which is a count."""

    ml_fraud_probability: float
    anomaly_score: float
    transaction_amount_anomaly: float
    transaction_frequency: float
    device_novelty: float
    location_anomaly: float
    transaction_time_anomaly: float


@dataclass(frozen=True)
class RuleMatch:
    code: str
    message: str
    score: float = 1.0

@dataclass(frozen=True)
class SignalContribution:
    name: str
    value: float
    risk_points: float
    explanation: str


Rule = Callable[[Mapping[str, Any]], RuleMatch | None]


@dataclass(frozen=True)
class RiskAssessment:
    risk_score: float
    risk_level: str
    decision: str
    reasons: tuple[str, ...]
    reason_codes: tuple[str, ...]
    signals: RiskSignals
    rule_matches: tuple[RuleMatch, ...]
    contributions: tuple[SignalContribution, ...]


class RuleEngine:
    """Evaluate independent, explainable transaction rules."""

    def __init__(self, rules: tuple[Rule, ...] = ()) -> None:
        self.rules = rules

    def evaluate(self, transaction: Mapping[str, Any]) -> tuple[RuleMatch, ...]:
        return tuple(
            match for rule in self.rules if (match := rule(transaction)) is not None
        )


class RiskEngine:
    """Combine model, behavioral, and rule signals into a decision."""

    DEFAULT_WEIGHTS = {
        "ml_fraud_probability": 0.30,
        "anomaly_score": 0.15,
        "transaction_amount_anomaly": 0.15,
        "transaction_frequency": 0.10,
        "device_novelty": 0.10,
        "location_anomaly": 0.10,
        "transaction_time_anomaly": 0.10,
    }

    def __init__(
        self,
        classifier: FraudClassifier | None = None,
        anomaly_detector: AnomalyDetector | None = None,
        rule_engine: RuleEngine | None = None,
        *,
        weights: Mapping[str, float] | None = None,
        anomaly_threshold: float = 0.5,
        frequency_saturation: float = 10.0,
        medium_threshold: float = 35.0,
        high_threshold: float = 70.0,
        rules_weight: float = 0.15,
    ) -> None:
        if not 0 <= medium_threshold <= high_threshold <= 100:
            raise ValueError("risk thresholds must satisfy 0 <= medium <= high <= 100")
        if frequency_saturation <= 0:
            raise ValueError("frequency_saturation must be positive")
        if rules_weight < 0:
            raise ValueError("rules_weight cannot be negative")
        supplied_weights = dict(weights or self.DEFAULT_WEIGHTS)
        if set(supplied_weights) != set(self.DEFAULT_WEIGHTS):
            raise ValueError("weights must define exactly the seven RiskSignals fields")
        if any(weight < 0 for weight in supplied_weights.values()) or not any(supplied_weights.values()):
            raise ValueError("weights must be non-negative and at least one must be positive")
        total = sum(supplied_weights.values())
        self.weights = {name: weight / total for name, weight in supplied_weights.items()}
        self.classifier = classifier
        self.anomaly_detector = anomaly_detector
        self.rule_engine = rule_engine or RuleEngine()
        self.anomaly_threshold = anomaly_threshold
        self.frequency_saturation = frequency_saturation
        self.medium_threshold = medium_threshold
        self.high_threshold = high_threshold
        self.rules_weight = rules_weight

    def score(self, signals: RiskSignals, transaction: Mapping[str, Any] | None = None) -> RiskAssessment:
        """Score explicit signals; every result includes reasons."""
        self._validate_signals(signals)
        matches = self.rule_engine.evaluate(transaction or {})
        values = {
            "ml_fraud_probability": signals.ml_fraud_probability,
            "anomaly_score": 1.0 if signals.anomaly_score > self.anomaly_threshold else 0.0,
            "transaction_amount_anomaly": signals.transaction_amount_anomaly,
            "transaction_frequency": min(signals.transaction_frequency / self.frequency_saturation, 1.0),
            "device_novelty": signals.device_novelty,
            "location_anomaly": signals.location_anomaly,
            "transaction_time_anomaly": signals.transaction_time_anomaly,
        }
        rule_signal = min(1.0, sum(max(0.0, match.score) for match in matches))
        weighted_signal = sum(self.weights[name] * value for name, value in values.items())
        risk_score = min(
            100.0,
            100.0 * (weighted_signal + self.rules_weight * rule_signal),
        )
        risk_level, decision = self._classify(risk_score)

        reasons = [
            f"{self._display_name(name)} contributed {value:.2f} risk"
            for name, value in values.items()
            if value > 0
        ]
        reasons.extend(match.message for match in matches)
        if not reasons:
            reasons.append("No elevated fraud, behavior, or rule signals detected")
        reason_codes = tuple(self._reason_code(name) for name, value in values.items() if value > 0)
        reason_codes += tuple(match.code for match in matches)
        contributions = tuple(
            SignalContribution(
                name=name,
                value=value,
                risk_points=100.0 * self.weights[name] * value,
                explanation=f"{self._display_name(name)} contributed {100.0 * self.weights[name] * value:.1f} risk points",
            )
            for name, value in values.items()
            if value > 0
        )
        return RiskAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            decision=decision,
            reasons=tuple(reasons),
            reason_codes=reason_codes,
            signals=signals,
            rule_matches=matches,
            contributions=contributions,
        )

    def assess(self, transaction: Mapping[str, Any], model_features: Any) -> RiskAssessment:
        """Adapt classifier and anomaly detector outputs into explicit signals."""
        return self.assess_with_features(
            transaction,
            model_features,
            RiskSignals(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        )

    def assess_with_features(
        self,
        transaction: Mapping[str, Any],
        model_features: Any,
        auxiliary_signals: RiskSignals,
    ) -> RiskAssessment:
        """Combine model outputs with already-computed transaction signals."""
        if self.classifier is None or self.anomaly_detector is None:
            raise RuntimeError("classifier and anomaly_detector are required for assess_with_features()")
        probability = float(self.classifier.predict_proba(model_features)[0][1])
        raw_anomaly_score = float(self.anomaly_detector.anomaly_score(model_features).iloc[0])
        anomaly_score = max(0.0, min(1.0, raw_anomaly_score))
        return self.score(
            RiskSignals(
                ml_fraud_probability=probability,
                anomaly_score=anomaly_score,
                transaction_amount_anomaly=auxiliary_signals.transaction_amount_anomaly,
                transaction_frequency=auxiliary_signals.transaction_frequency,
                device_novelty=auxiliary_signals.device_novelty,
                location_anomaly=auxiliary_signals.location_anomaly,
                transaction_time_anomaly=auxiliary_signals.transaction_time_anomaly,
            ),
            transaction,
        )

    def _classify(self, risk_score: float) -> tuple[str, str]:
        if risk_score >= self.high_threshold:
            return "HIGH", "BLOCK"
        if risk_score >= self.medium_threshold:
            return "MEDIUM", "REVIEW"
        return "LOW", "APPROVE"

    def _validate_signals(self, signals: RiskSignals) -> None:
        for name, value in vars(signals).items():
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")
            if name != "transaction_frequency" and not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
            if name == "transaction_frequency" and value < 0:
                raise ValueError("transaction_frequency cannot be negative")

    def _display_name(self, name: str) -> str:
        return name.replace("_", " ").capitalize()

    def _reason_code(self, name: str) -> str:
        return name.upper()
