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
    """Normalized evidence inputs, except transaction frequency which is a count."""

    ml_fraud_probability: float
    anomaly_score: float
    transaction_amount_anomaly: float
    transaction_frequency: float
    device_novelty: float
    location_anomaly: float
    transaction_time_anomaly: float
    behavior_deviation: float = 0.0
    temporal_evidence: float = 0.0
    network_evidence: float = 0.0
    merchant_intelligence: float = 0.0
    device_intelligence: float = 0.0


@dataclass(frozen=True)
class EvidenceSignal:
    code: str
    category: str
    score: float
    severity: str
    explanation: str


@dataclass(frozen=True)
class DecisionPolicy:
    """Probability and economics policy; supporting evidence can only adjust risk modestly."""

    review_probability: float = 0.35
    block_probability: float = 0.75
    review_expected_loss: float = 100.0
    block_expected_loss: float = 1000.0
    false_positive_cost: float = 25.0
    fraud_loss_multiplier: float = 1.0
    maximum_supporting_uplift: float = 0.15

    def __post_init__(self) -> None:
        if not 0 <= self.review_probability <= self.block_probability <= 1:
            raise ValueError("probability thresholds must satisfy 0 <= review <= block <= 1")
        if self.review_expected_loss < 0 or self.block_expected_loss < 0:
            raise ValueError("expected-loss thresholds cannot be negative")
        if self.false_positive_cost < 0 or self.fraud_loss_multiplier <= 0:
            raise ValueError("decision economics must be non-negative and loss multiplier positive")
        if not 0 <= self.maximum_supporting_uplift <= 1:
            raise ValueError("maximum supporting uplift must be between 0 and 1")


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
    fraud_probability: float
    risk_level: str
    decision: str
    reasons: tuple[str, ...]
    reason_codes: tuple[str, ...]
    signals: RiskSignals
    rule_matches: tuple[RuleMatch, ...]
    contributions: tuple[SignalContribution, ...]
    evidence: tuple[EvidenceSignal, ...]
    explanation: dict[str, Any]


class RuleEngine:
    """Evaluate independent, explainable transaction rules."""

    def __init__(self, rules: tuple[Rule, ...] = ()) -> None:
        self.rules = rules

    def evaluate(self, transaction: Mapping[str, Any]) -> tuple[RuleMatch, ...]:
        return tuple(
            match for rule in self.rules if (match := rule(transaction)) is not None
        )


class RiskEngine:
    """Fuse calibrated model probability with bounded, observable supporting evidence."""

    def __init__(
        self,
        classifier: FraudClassifier | None = None,
        anomaly_detector: AnomalyDetector | None = None,
        rule_engine: RuleEngine | None = None,
        *,
        calibrator: Any | None = None,
        policy: DecisionPolicy | None = None,
        anomaly_threshold: float = 0.5,
        frequency_saturation: float = 10.0,
        medium_threshold: float | None = None,
        high_threshold: float | None = None,
    ) -> None:
        if frequency_saturation <= 0:
            raise ValueError("frequency_saturation must be positive")
        self.classifier = classifier
        self.anomaly_detector = anomaly_detector
        self.rule_engine = rule_engine or RuleEngine()
        self.calibrator = calibrator
        self.policy = policy or DecisionPolicy()
        self.anomaly_threshold = anomaly_threshold
        self.frequency_saturation = frequency_saturation
        self.legacy_medium_threshold = medium_threshold if medium_threshold is not None else 35.0
        self.legacy_high_threshold = high_threshold if high_threshold is not None else 70.0
        if not 0 <= self.legacy_medium_threshold <= self.legacy_high_threshold <= 100:
            raise ValueError("risk thresholds must satisfy 0 <= medium <= high <= 100")

    def score(self, signals: RiskSignals, transaction: Mapping[str, Any] | None = None) -> RiskAssessment:
        """Score explicit signals; legacy-only callers retain the historical contract."""
        legacy_auxiliary = (
            signals.anomaly_score,
            signals.transaction_amount_anomaly,
            signals.transaction_frequency,
            signals.device_novelty,
            signals.location_anomaly,
            signals.transaction_time_anomaly,
        )
        if signals.ml_fraud_probability > 0 and not any(legacy_auxiliary):
            return self._fuse(signals, transaction)
        if not any((signals.behavior_deviation, signals.temporal_evidence, signals.network_evidence, signals.merchant_intelligence, signals.device_intelligence)):
            return self._legacy_score(signals, transaction)
        return self._fuse(signals, transaction)

    def _fuse(self, signals: RiskSignals, transaction: Mapping[str, Any] | None = None) -> RiskAssessment:
        """Apply the probability-first policy to model and supporting evidence."""
        self._validate_signals(signals)
        matches = self.rule_engine.evaluate(transaction or {})
        amount = float((transaction or {}).get("amount", 0) or 0)
        evidence = self._evidence(signals, matches)
        evidence_severity = max((self._severity_value(item.severity) for item in evidence), default=0.0)
        expected_loss = signals.ml_fraud_probability * max(0.0, amount) * self.policy.fraud_loss_multiplier
        economic_threshold = self._economic_probability_threshold(amount)
        risk_probability = min(
            1.0,
            signals.ml_fraud_probability
            + self.policy.maximum_supporting_uplift * (1.0 - signals.ml_fraud_probability) * evidence_severity,
        )
        risk_level, decision = self._classify(
            signals.ml_fraud_probability,
            expected_loss,
            evidence_severity,
            economic_threshold,
        )
        reasons = [item.explanation for item in evidence]
        if not reasons:
            reasons.append("No elevated fraud evidence was observed")
        reason_codes = tuple(item.code for item in evidence)
        contributions = tuple(
            SignalContribution(
                name=item.category,
                value=item.score,
                risk_points=round(100.0 * self.policy.maximum_supporting_uplift * item.score, 2),
                explanation=item.explanation,
            )
            for item in evidence
        )
        return RiskAssessment(
            risk_score=round(risk_probability * 100.0, 2),
            fraud_probability=signals.ml_fraud_probability,
            risk_level=risk_level,
            decision=decision,
            reasons=tuple(reasons),
            reason_codes=reason_codes,
            signals=signals,
            rule_matches=matches,
            contributions=contributions,
            evidence=tuple(evidence),
            explanation={
                "fraud_probability": signals.ml_fraud_probability,
                "expected_loss": round(expected_loss, 2),
                "economic_probability_threshold": round(economic_threshold, 4),
                "supporting_evidence_severity": round(evidence_severity, 4),
                "evidence": [vars(item) for item in evidence],
                "basis": "Calibrated fraud probability is primary; supporting evidence is bounded and observable.",
            },
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
        probability = self.calibrate(float(self.classifier.predict_proba(model_features)[0][1]))
        raw_anomaly_score = float(self.anomaly_detector.anomaly_score(model_features).iloc[0])
        anomaly_score = max(0.0, min(1.0, raw_anomaly_score))
        return self._fuse(
            RiskSignals(
                ml_fraud_probability=probability,
                anomaly_score=anomaly_score,
                transaction_amount_anomaly=auxiliary_signals.transaction_amount_anomaly,
                transaction_frequency=auxiliary_signals.transaction_frequency,
                device_novelty=auxiliary_signals.device_novelty,
                location_anomaly=auxiliary_signals.location_anomaly,
                transaction_time_anomaly=auxiliary_signals.transaction_time_anomaly,
                behavior_deviation=auxiliary_signals.behavior_deviation,
                temporal_evidence=auxiliary_signals.temporal_evidence,
                network_evidence=auxiliary_signals.network_evidence,
                merchant_intelligence=auxiliary_signals.merchant_intelligence,
                device_intelligence=auxiliary_signals.device_intelligence,
            ),
            transaction,
        )

    def _legacy_score(self, signals: RiskSignals, transaction: Mapping[str, Any] | None) -> RiskAssessment:
        """Compatibility adapter for callers that still submit only the original seven signals."""
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
        weights = (0.30, 0.15, 0.15, 0.10, 0.10, 0.10, 0.10)
        risk_score = min(100.0, 100.0 * sum(weight * value for weight, value in zip(weights, values.values())))
        risk_level, decision = ("HIGH", "BLOCK") if risk_score >= self.legacy_high_threshold else ("MEDIUM", "REVIEW") if risk_score >= self.legacy_medium_threshold else ("LOW", "APPROVE")
        evidence = self._evidence(signals, matches)
        reasons = tuple(item.explanation for item in evidence) or ("No elevated fraud evidence was observed",)
        reason_codes = tuple(item.code for item in evidence)
        if signals.ml_fraud_probability > 0:
            reason_codes = ("ML_FRAUD_PROBABILITY",) + reason_codes
        return RiskAssessment(
            risk_score=risk_score,
            fraud_probability=signals.ml_fraud_probability,
            risk_level=risk_level,
            decision=decision,
            reasons=reasons,
            reason_codes=reason_codes,
            signals=signals,
            rule_matches=matches,
            contributions=tuple(
                SignalContribution(name=name, value=value, risk_points=100.0 * weight * value, explanation=f"{self._display_name(name)} contributed {100.0 * weight * value:.1f} risk points")
                for (name, value), weight in zip(values.items(), weights) if value > 0
            ),
            evidence=tuple(evidence),
            explanation={"fraud_probability": signals.ml_fraud_probability, "basis": "Legacy compatibility score; model-backed assessments use probability-first fusion."},
        )

    @staticmethod
    def _display_name(name: str) -> str:
        return name.replace("_", " ").capitalize()

    def calibrate(self, probability: float) -> float:
        if not isfinite(probability):
            raise ValueError("fraud probability must be finite")
        probability = min(1.0, max(0.0, probability))
        if self.calibrator is None:
            return probability
        if hasattr(self.calibrator, "predict_proba"):
            return min(1.0, max(0.0, float(self.calibrator.predict_proba([[probability]])[0][1])))
        return min(1.0, max(0.0, float(self.calibrator.predict([probability])[0])))

    def _classify(self, probability: float, expected_loss: float, evidence_severity: float, economic_threshold: float) -> tuple[str, str]:
        if probability >= self.policy.block_probability or (
            probability >= economic_threshold
            and expected_loss >= self.policy.block_expected_loss
            and evidence_severity >= 0.5
        ):
            return "HIGH", "BLOCK"
        if probability >= self.policy.review_probability or expected_loss >= self.policy.review_expected_loss or evidence_severity >= 0.75:
            return "MEDIUM", "REVIEW"
        return "LOW", "APPROVE"

    def _economic_probability_threshold(self, amount: float) -> float:
        denominator = self.policy.false_positive_cost + max(0.0, amount) * self.policy.fraud_loss_multiplier
        return self.policy.false_positive_cost / denominator if denominator else 1.0

    def _evidence(self, signals: RiskSignals, matches: tuple[RuleMatch, ...]) -> list[EvidenceSignal]:
        candidates = (
            ("ANOMALY_DETECTED", "anomaly_detection", signals.anomaly_score, "high", "Anomaly detection score is elevated"),
            ("BEHAVIOR_DEVIATION", "behavioral_deviation", signals.behavior_deviation, "medium", "Behavioral deviation detected"),
            ("TEMPORAL_VELOCITY", "temporal_velocity", max(signals.temporal_evidence, min(signals.transaction_frequency / self.frequency_saturation, 1.0)), "high", "Transaction velocity is above the observed baseline"),
            ("NETWORK_EVIDENCE", "network", signals.network_evidence, "high", "Network relationship evidence is elevated"),
            ("MERCHANT_INTELLIGENCE", "merchant_intelligence", signals.merchant_intelligence, "medium", "Merchant intelligence signal is elevated"),
            ("DEVICE_INTELLIGENCE", "device_intelligence", max(signals.device_intelligence, signals.device_novelty), "medium", "Device intelligence signal is elevated"),
            ("AMOUNT_ANOMALY", "transaction_context", signals.transaction_amount_anomaly, "medium", "Transaction amount is anomalous"),
            ("LOCATION_ANOMALY", "transaction_context", signals.location_anomaly, "medium", "Transaction location is anomalous"),
            ("UNUSUAL_TIME", "transaction_context", signals.transaction_time_anomaly, "low", "Transaction time is unusual"),
        )
        evidence = [EvidenceSignal(code, category, round(max(0.0, min(score, 1.0)), 4), severity, explanation) for code, category, score, severity, explanation in candidates if score > 0]
        evidence.extend(EvidenceSignal(match.code, "rule_violation", round(max(0.0, min(match.score, 1.0)), 4), "high", match.message) for match in matches)
        return evidence

    @staticmethod
    def _severity_value(severity: str) -> float:
        return {"low": 0.25, "medium": 0.5, "high": 1.0}.get(severity, 0.0)

    def _validate_signals(self, signals: RiskSignals) -> None:
        for name, value in vars(signals).items():
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")
            if name != "transaction_frequency" and not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
            if name == "transaction_frequency" and value < 0:
                raise ValueError("transaction_frequency cannot be negative")

