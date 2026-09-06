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
        self.training_score_range_: tuple[float, float] = (0.0, 1.0)
        self.training_rows_: int = 0
        self.fit_on_legitimate_only_: bool = False

    def fit(self, transactions: pd.DataFrame) -> "IsolationForestAnomalyDetector":
        labels = next(
            (column for column in ("Class", "class", "is_fraud", "fraud") if column in transactions),
            None,
        )
        training_transactions = transactions
        if labels is not None:
            legitimate = pd.to_numeric(transactions[labels], errors="coerce").eq(0)
            if legitimate.any():
                training_transactions = transactions.loc[legitimate]
                self.fit_on_legitimate_only_ = True
        features = prepare_transaction_features(transactions)
        training_features = prepare_transaction_features(training_transactions)
        self.feature_names_ = list(features.columns)
        self.training_rows_ = len(training_features)
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
        self.pipeline.fit(training_features)
        training_raw_scores = -self.pipeline.decision_function(training_features)
        lower, upper = pd.Series(training_raw_scores).quantile([0.01, 0.99]).tolist()
        self.training_score_range_ = (float(lower), float(max(upper, lower + 1e-9)))
        return self

    def _require_fitted(self) -> Pipeline:
        if self.pipeline is None:
            raise RuntimeError("fit must be called before scoring transactions")
        return self.pipeline

    def anomaly_score(self, transactions: pd.DataFrame) -> pd.Series:
        """Return scores where larger values indicate more anomalous behavior."""
        pipeline = self._require_fitted()
        features = prepare_transaction_features(transactions)
        raw_scores = -pipeline.decision_function(features)
        lower, upper = self.training_score_range_
        scores = ((raw_scores - lower) / (upper - lower)).clip(0.0, 1.0 - 1e-12)
        return pd.Series(scores, index=transactions.index, name="anomaly_score")

    def top_anomaly_features(
        self, transactions: pd.DataFrame, top_n: int = 3
    ) -> list[list[dict[str, float | str]]]:
        """Return the largest absolute standardized deviations per transaction."""
        if top_n <= 0:
            raise ValueError("top_n must be positive")
        pipeline = self._require_fitted()
        features = prepare_transaction_features(transactions).reindex(columns=self.feature_names_)
        imputed = pipeline.named_steps["imputer"].transform(features)
        scaled = pipeline.named_steps["scaler"].transform(imputed)
        results: list[list[dict[str, float | str]]] = []
        for row in scaled:
            indices = sorted(range(len(row)), key=lambda index: abs(row[index]), reverse=True)[:top_n]
            results.append(
                [
                    {"feature": self.feature_names_[index], "deviation": round(float(abs(row[index])), 6)}
                    for index in indices
                    if abs(row[index]) > 0
                ]
            )
        return results

    def predict_anomalies(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """Return input rows with an anomaly score and threshold decision."""
        scores = self.anomaly_score(transactions)
        result = transactions.copy()
        result["anomaly_score"] = scores
        result["top_anomaly_features"] = self.top_anomaly_features(transactions)
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
            "training_rows": self.training_rows_,
            "fit_on_legitimate_only": self.fit_on_legitimate_only_,
            "training_score_range": self.training_score_range_,
        }
