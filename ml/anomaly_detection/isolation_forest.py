"""Unsupervised transaction anomaly detection with Isolation Forest."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def prepare_transaction_features(transactions: pd.DataFrame) -> pd.DataFrame:
    """Create behavior features without using a supervised fraud label.

    Numeric transaction fields are retained. Time and amount receive additional
    behavior features when those conventional column names are present.
    """
    if transactions.empty:
        raise ValueError("transactions must contain at least one row")

    features = transactions.copy()
    label_columns = [column for column in ("Class", "class", "is_fraud", "fraud") if column in features]
    features = features.drop(columns=label_columns)
    numeric_features = features.select_dtypes(include="number").copy()
    if numeric_features.empty:
        raise ValueError("transactions must contain numeric behavior features")

    if "Time" in numeric_features:
        numeric_features["hour"] = (numeric_features["Time"] / 3600).mod(24)
        numeric_features["day"] = (numeric_features["Time"] / 86400).astype("int64")
        numeric_features = numeric_features.drop(columns=["Time"])
    if "Amount" in numeric_features:
        numeric_features["amount_log1p"] = numeric_features["Amount"].clip(lower=0).map(math.log1p)
        numeric_features["amount_missing"] = numeric_features["Amount"].isna().astype("int8")

    return numeric_features


class IsolationForestAnomalyDetector:
    """Independent unsupervised detector for transaction behavior anomalies.

    ``anomaly_score`` is higher for more unusual behavior. The threshold is
    deliberately separate from the supervised classifier's fraud probability.
    """

    def __init__(
        self,
        *,
        contamination: float | str = "auto",
        threshold: float = 0.0,
        n_estimators: int = 200,
        random_state: int = 42,
    ) -> None:
        if isinstance(contamination, float) and not 0 < contamination <= 0.5:
            raise ValueError("contamination must be between 0 and 0.5")
        if n_estimators <= 0:
            raise ValueError("n_estimators must be positive")
        self.contamination = contamination
        self.threshold = threshold
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.pipeline: Pipeline | None = None
        self.feature_names_: list[str] = []

    def fit(self, transactions: pd.DataFrame) -> "IsolationForestAnomalyDetector":
        features = prepare_transaction_features(transactions)
        self.feature_names_ = list(features.columns)
        self.pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "isolation_forest",
                    IsolationForest(
                        contamination=self.contamination,
                        n_estimators=self.n_estimators,
                        random_state=self.random_state,
                    ),
                ),
            ]
        )
        self.pipeline.fit(features)
        return self

    def _require_fitted(self) -> Pipeline:
        if self.pipeline is None:
            raise RuntimeError("fit must be called before scoring transactions")
        return self.pipeline

    def anomaly_score(self, transactions: pd.DataFrame) -> pd.Series:
        """Return scores where larger values indicate more anomalous behavior."""
        pipeline = self._require_fitted()
        features = prepare_transaction_features(transactions)
        scores = -pipeline.decision_function(features)
        return pd.Series(scores, index=transactions.index, name="anomaly_score")

    def predict_anomalies(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """Return input rows with an anomaly score and threshold decision."""
        scores = self.anomaly_score(transactions)
        result = transactions.copy()
        result["anomaly_score"] = scores
        result["is_anomaly"] = scores >= self.threshold
        return result

    def save(self, path: str | Path) -> None:
        self._require_fitted()
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str | Path) -> "IsolationForestAnomalyDetector":
        detector = joblib.load(path)
        if not isinstance(detector, cls):
            raise TypeError("artifact is not an IsolationForestAnomalyDetector")
        return detector

    def configuration(self) -> dict[str, Any]:
        return {
            "contamination": self.contamination,
            "threshold": self.threshold,
            "n_estimators": self.n_estimators,
            "random_state": self.random_state,
            "feature_names": self.feature_names_,
        }
