from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.services.risk_engine import RiskEngine, RuleEngine, RuleMatch


def _high_amount(transaction: dict[str, Any]) -> RuleMatch | None:
    if float(transaction.get("amount", 0)) >= 50000:
        return RuleMatch("HIGH_AMOUNT", "High transaction amount", 0.7)
    return None


def _new_device(transaction: dict[str, Any]) -> RuleMatch | None:
    if transaction.get("device_status") == "new":
        return RuleMatch("NEW_DEVICE", "New device requires verification", 0.7)
    return None


def _unusual_time(transaction: dict[str, Any]) -> RuleMatch | None:
    occurred_at = transaction.get("occurred_at")
    if hasattr(occurred_at, "hour") and occurred_at.hour < 6:
        return RuleMatch("UNUSUAL_TIME", "Transaction occurred during unusual hours", 0.5)
    return None


def _velocity(transaction: dict[str, Any]) -> RuleMatch | None:
    if float(transaction.get("transaction_frequency", 0)) >= 5:
        return RuleMatch("VELOCITY_ANOMALY", "Transaction velocity is above the normal range", 0.8)
    return None


def _impossible_travel(transaction: dict[str, Any]) -> RuleMatch | None:
    if transaction.get("impossible_travel"):
        return RuleMatch("IMPOSSIBLE_TRAVEL", "Location changed too quickly to be plausible", 1.0)
    return None


def _behavior_deviation(transaction: dict[str, Any]) -> RuleMatch | None:
    if transaction.get("behavior_deviation"):
        return RuleMatch("BEHAVIOR_DEVIATION", "Transaction differs significantly from user history", 0.7)
    return None


class ModelRuntime:
    """Load the separately trained supervised and anomaly artifacts."""

    def __init__(self, root: Path) -> None:
        model_dir = root / "ml" / "models"
        classifier_path = model_dir / "fraud_model.joblib"
        anomaly_path = model_dir / "anomaly_detector.joblib"
        metadata_path = model_dir / "model_version.json"
        if not classifier_path.exists() or not anomaly_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(
                "trained fraud_model.joblib, anomaly_detector.joblib, and model_version.json artifacts are required"
            )
        self.classifier = joblib.load(classifier_path)
        self.anomaly_detector = joblib.load(anomaly_path)
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.model_version = str(self.metadata["model_version"])
        self.decision_threshold = float(self.metadata["decision_threshold"])
        if not 0 < self.decision_threshold < 1:
            raise ValueError("model decision threshold must be between 0 and 1")
        self.risk_engine = RiskEngine(
            self.classifier,
            self.anomaly_detector,
            RuleEngine((_high_amount, _new_device, _unusual_time, _velocity, _impossible_travel, _behavior_deviation)),
        )

    def model_features(self, transaction: dict[str, Any]) -> pd.DataFrame:
        preprocessor = self.classifier.named_steps["preprocessor"]
        feature_names = list(preprocessor.feature_names_in_)
        features = {name: 0.0 for name in feature_names}
        for name, value in transaction.items():
            if name in features and isinstance(value, (int, float)):
                features[name] = value
        if "hour" in features:
            occurred_at = transaction.get("occurred_at")
            features["hour"] = occurred_at.hour if hasattr(occurred_at, "hour") else 0.0
        if "day" in features:
            occurred_at = transaction.get("occurred_at")
            features["day"] = occurred_at.timetuple().tm_yday if hasattr(occurred_at, "timetuple") else 0.0
        if "amount_log1p" in features:
            amount = float(transaction.get("Amount", transaction.get("amount", 0)))
            features["amount_log1p"] = __import__("math").log1p(max(0.0, amount))
        return pd.DataFrame([features], columns=feature_names)

    def assess(self, transaction: dict[str, Any]):
        features = self.model_features(transaction)
        return self.risk_engine.assess(transaction, features)

    def predict(self, features: dict[str, float]) -> tuple[float, str, str]:
        """Predict only from caller-provided model features; never synthesize missing inputs."""
        expected = set(self.metadata["feature_names"])
        missing = sorted(expected.difference(features))
        if missing:
            raise ValueError(f"missing required model features: {', '.join(missing)}")
        frame = pd.DataFrame([{name: features[name] for name in expected}], columns=sorted(expected))
        probability = float(self.classifier.predict_proba(frame)[0][1])
        decision = "BLOCK" if probability >= self.decision_threshold else "APPROVE"
        risk_level = "HIGH" if decision == "BLOCK" else "LOW"
        return probability, decision, risk_level

    def predict_intelligence(
        self, features: dict[str, float]
    ) -> tuple[float, str, str, float, str, list[dict[str, float | str]]]:
        probability, decision, risk_level = self.predict(features)
        anomaly_frame = pd.DataFrame(
            [{name: features[name] for name in self.anomaly_detector.feature_names_}],
            columns=self.anomaly_detector.feature_names_,
        )
        anomaly_score = float(self.anomaly_detector.anomaly_score(anomaly_frame).iloc[0])
        anomaly_level = (
            "HIGH" if anomaly_score >= 0.8 else "MEDIUM" if anomaly_score >= 0.5 else "LOW"
        )
        top_features = self.anomaly_detector.top_anomaly_features(anomaly_frame)[0]
        return probability, decision, risk_level, anomaly_score, anomaly_level, top_features
