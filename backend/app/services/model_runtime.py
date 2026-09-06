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
        calibrator_path = model_dir / "fraud_calibrator.joblib"
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
        self.calibrator = joblib.load(calibrator_path) if calibrator_path.exists() else None
        self.risk_engine = RiskEngine(
            self.classifier,
            self.anomaly_detector,
            RuleEngine((_high_amount, _new_device, _unusual_time, _velocity, _impossible_travel, _behavior_deviation)),
            calibrator=self.calibrator,
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
        assessment = self.risk_engine.assess(transaction, features)
        assessment.explanation["model_attributions"] = self.explain_features(features)
        anomaly_factors = self.anomaly_detector.feature_attributions(features)[0]
        assessment.explanation["anomaly_attributions"] = anomaly_factors
        assessment.explanation["top_contributing_factors"] = assessment.explanation["model_attributions"]
        assessment.explanation["lower_risk_signals"] = [
            item for item in assessment.explanation["model_attributions"]
            if item.get("direction") == "decreases_risk"
        ]
        return assessment

    def explain_prediction(self, features: dict[str, float]) -> dict[str, Any]:
        expected = set(self.metadata["feature_names"])
        missing = sorted(expected.difference(features))
        if missing:
            raise ValueError(f"missing required model features: {', '.join(missing)}")
        frame = pd.DataFrame([{name: features[name] for name in expected}], columns=sorted(expected))
        anomaly_frame = pd.DataFrame(
            [{name: features[name] for name in self.anomaly_detector.feature_names_}],
            columns=self.anomaly_detector.feature_names_,
        )
        model_factors = self.explain_features(frame)
        lower_risk = [item for item in model_factors if item["direction"] == "decreases_risk"]
        return {
            "top_contributing_factors": model_factors,
            "lower_risk_signals": lower_risk,
            "anomaly_factors": self.anomaly_detector.feature_attributions(anomaly_frame)[0],
            "basis": "Attributions are calculated from the selected model and anomaly detector inputs.",
        }

    def explain_features(self, features: pd.DataFrame, top_n: int = 5) -> list[dict[str, Any]]:
        """Explain actual model inputs with SHAP when available, otherwise ablation."""
        if top_n <= 0:
            raise ValueError("top_n must be positive")
        full_probability = self.risk_engine.calibrate(float(self.classifier.predict_proba(features)[0][1]))
        attributions: list[dict[str, Any]] = []
        try:
            import shap

            preprocessor = self.classifier.named_steps["preprocessor"]
            classifier = self.classifier.named_steps["classifier"]
            transformed = preprocessor.transform(features)
            values = shap.TreeExplainer(classifier).shap_values(transformed)
            if isinstance(values, list):
                values = values[1]
            if getattr(values, "ndim", 0) == 3:
                values = values[:, :, 1]
            names = list(preprocessor.get_feature_names_out())
            row = values[0]
            for index in sorted(range(len(row)), key=lambda item: abs(row[item]), reverse=True)[:top_n]:
                contribution = float(row[index])
                if contribution == 0:
                    continue
                attributions.append({
                    "feature": names[index].split("__", 1)[-1],
                    "direction": "increases_risk" if contribution > 0 else "decreases_risk",
                    "contribution": round(contribution, 6),
                    "relative_contribution": 0.0,
                    "source": "shap",
                })
        except (ImportError, AttributeError, TypeError, ValueError, RuntimeError):
            baseline = self._baseline_frame(features)
            for name in features.columns:
                ablated = features.copy()
                ablated.loc[:, name] = baseline.loc[:, name]
                probability = self.risk_engine.calibrate(float(self.classifier.predict_proba(ablated)[0][1]))
                contribution = full_probability - probability
                if contribution == 0:
                    continue
                attributions.append({
                    "feature": name,
                    "direction": "increases_risk" if contribution > 0 else "decreases_risk",
                    "contribution": round(contribution, 6),
                    "relative_contribution": 0.0,
                    "source": "model_ablation",
                })
            attributions.sort(key=lambda item: abs(item["contribution"]), reverse=True)
            attributions = attributions[:top_n]
        total = sum(abs(float(item["contribution"])) for item in attributions) or 1.0
        for item in attributions:
            item["relative_contribution"] = round(abs(float(item["contribution"])) / total, 6)
        return attributions

    def _baseline_frame(self, features: pd.DataFrame) -> pd.DataFrame:
        baseline = features.copy()
        preprocessor = self.classifier.named_steps["preprocessor"]
        for _, transformer, columns in getattr(preprocessor, "transformers_", []):
            if transformer == "drop" or transformer == "passthrough":
                continue
            statistics = getattr(getattr(transformer, "named_steps", {}).get("imputer"), "statistics_", None)
            if statistics is None:
                continue
            for name, value in zip(columns, statistics):
                if name in baseline.columns and pd.notna(value):
                    baseline.loc[:, name] = float(value)
        return baseline

    def predict(self, features: dict[str, float]) -> tuple[float, str, str]:
        """Predict only from caller-provided model features; never synthesize missing inputs."""
        expected = set(self.metadata["feature_names"])
        missing = sorted(expected.difference(features))
        if missing:
            raise ValueError(f"missing required model features: {', '.join(missing)}")
        frame = pd.DataFrame([{name: features[name] for name in expected}], columns=sorted(expected))
        probability = self.risk_engine.calibrate(float(self.classifier.predict_proba(frame)[0][1]))
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
