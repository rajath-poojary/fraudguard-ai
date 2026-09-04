from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.services.risk_engine import RiskEngine


class ModelRuntime:
    """Load the separately trained supervised and anomaly artifacts."""

    def __init__(self, root: Path) -> None:
        model_dir = root / "ml" / "models"
        classifier_path = model_dir / "fraud_model.joblib"
        anomaly_path = model_dir / "anomaly_detector.joblib"
        if not classifier_path.exists() or not anomaly_path.exists():
            raise FileNotFoundError(
                "trained fraud_model.joblib and anomaly_detector.joblib artifacts are required"
            )
        self.classifier = joblib.load(classifier_path)
        self.anomaly_detector = joblib.load(anomaly_path)
        self.risk_engine = RiskEngine(self.classifier, self.anomaly_detector)

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
