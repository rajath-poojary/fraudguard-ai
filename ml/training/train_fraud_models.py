"""Train and evaluate fraud classifiers on a public transaction dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier

SEED = 42
DATASET_URL = "https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv"
TARGET_COLUMN = "Class"


class TrainingError(RuntimeError):
    """Raised when the dataset cannot be used for training."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, help="Local CSV path; downloads the public dataset when omitted")
    parser.add_argument("--data-url", default=DATASET_URL, help="Public CSV URL used when --data is omitted")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=SEED)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def obtain_dataset(data_path: Path | None, data_url: str, raw_dir: Path) -> Path:
    if data_path is not None:
        if not data_path.is_file():
            raise TrainingError(f"Dataset not found: {data_path}")
        return data_path

    raw_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_dir / "creditcard.csv"
    if not destination.exists():
        print(f"Downloading dataset from {data_url}")
        urllib.request.urlretrieve(data_url, destination)
    return destination


def engineer_features(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    if TARGET_COLUMN not in data.columns:
        raise TrainingError(f"Dataset must contain a '{TARGET_COLUMN}' target column")

    frame = data.copy()
    missing_before = int(frame.isna().sum().sum())
    target = pd.to_numeric(frame.pop(TARGET_COLUMN), errors="coerce")
    valid_target = target.notna()
    frame = frame.loc[valid_target].reset_index(drop=True)
    target = target.loc[valid_target].astype(int).reset_index(drop=True)

    if not set(target.unique()).issubset({0, 1}):
        raise TrainingError("The target column must contain only binary 0/1 labels")
    if target.nunique() < 2:
        raise TrainingError("The dataset must contain both legitimate and fraudulent transactions")

    if "Time" in frame.columns:
        frame["hour"] = (frame["Time"] / 3600).mod(24)
        frame["day"] = (frame["Time"] / 86400).astype("int64")
        frame = frame.drop(columns=["Time"])
    if "Amount" in frame.columns:
        frame["amount_log1p"] = (frame["Amount"].clip(lower=0)).map(lambda value: __import__("math").log1p(value))
        frame["amount_missing"] = frame["Amount"].isna().astype("int8")

    missing_after_feature_engineering = int(frame.isna().sum().sum())
    details = {
        "rows": int(len(frame)),
        "features": int(frame.shape[1]),
        "missing_values_before": missing_before,
        "missing_values_before_imputation": missing_after_feature_engineering,
        "legitimate_transactions": int((target == 0).sum()),
        "fraudulent_transactions": int((target == 1).sum()),
        "fraud_rate": float(target.mean()),
    }
    return frame, target, details


def make_preprocessor(feature_names: list[str]) -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    return ColumnTransformer(
        transformers=[("numeric", numeric_pipeline, feature_names)],
        remainder="drop",
    )


def evaluate_model(model: Pipeline, x_test: pd.DataFrame, y_test: pd.Series) -> dict[str, Any]:
    predictions = model.predict(x_test)
    probabilities = model.predict_proba(x_test)[:, 1]
    matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
    return {
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "confusion_matrix": matrix.tolist(),
    }


def train_models(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    random_state: int,
) -> dict[str, dict[str, Any]]:
    model_factories = {
        "logistic_regression": lambda: LogisticRegression(
            class_weight="balanced", max_iter=1000, random_state=random_state
        ),
        "decision_tree": lambda: DecisionTreeClassifier(
            class_weight="balanced", random_state=random_state
        ),
        "random_forest": lambda: RandomForestClassifier(
            class_weight="balanced_subsample",
            n_estimators=200,
            n_jobs=-1,
            random_state=random_state,
        ),
    }
    results: dict[str, dict[str, Any]] = {}
    for name, factory in model_factories.items():
        pipeline = Pipeline(
            steps=[
                ("preprocessor", make_preprocessor(list(x_train.columns))),
                ("classifier", factory()),
            ]
        )
        pipeline.fit(x_train, y_train)
        results[name] = {
            "metrics": evaluate_model(pipeline, x_test, y_test),
            "pipeline": pipeline,
        }
    return results


def select_model(results: dict[str, dict[str, Any]]) -> str:
    return max(
        results,
        key=lambda name: (
            results[name]["metrics"]["f1"],
            results[name]["metrics"]["recall"],
            results[name]["metrics"]["roc_auc"],
            results[name]["metrics"]["precision"],
        ),
    )


def write_artifacts(
    results: dict[str, dict[str, Any]],
    selected_name: str,
    dataset_path: Path,
    dataset_details: dict[str, Any],
    test_size: float,
    random_state: int,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_pipeline: Pipeline = results[selected_name]["pipeline"]
    joblib.dump(selected_pipeline, output_dir / "fraud_model.joblib")
    joblib.dump(selected_pipeline.named_steps["preprocessor"], output_dir / "fraud_preprocessor.joblib")

    metrics = {
        "dataset": {
            **dataset_details,
            "path": str(dataset_path),
            "sha256": sha256_file(dataset_path),
        },
        "split": {"test_size": test_size, "random_state": random_state, "stratified": True},
        "selection_rule": "highest fraud F1, then recall, ROC-AUC, and precision",
        "selected_model": selected_name,
        "models": {name: value["metrics"] for name, value in results.items()},
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    report = [
        "# Fraud model evaluation report",
        "",
        "This report was generated by `ml/training/train_fraud_models.py`; metrics are computed from the recorded test split.",
        "",
        "## Dataset and preparation",
        f"- Source file: `{dataset_path}`",
        f"- SHA-256: `{metrics['dataset']['sha256']}`",
        f"- Rows: {dataset_details['rows']}; features after engineering: {dataset_details['features']}",
        f"- Legitimate: {dataset_details['legitimate_transactions']}; fraudulent: {dataset_details['fraudulent_transactions']} ({dataset_details['fraud_rate']:.6%})",
        f"- Missing values before imputation: {dataset_details['missing_values_before_imputation']}",
        "- Features: time-derived hour/day, log-transformed amount, and amount-missing indicator; remaining numeric missing values use median imputation and standardization.",
        "",
        "## Holdout results",
        "",
        "| Model | Precision | Recall | F1 | ROC-AUC | Confusion matrix [TN, FP; FN, TP] |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for name, value in results.items():
        metric = value["metrics"]
        report.append(
            f"| {name} | {metric['precision']:.6f} | {metric['recall']:.6f} | {metric['f1']:.6f} | {metric['roc_auc']:.6f} | {metric['confusion_matrix']} |"
        )
    report.extend(
        [
            "",
            f"## Selected model",
            "",
            f"`{selected_name}` was selected using fraud F1 as the primary criterion, followed by recall, ROC-AUC, and precision. F1 balances missed fraud against false alerts while retaining recall as the first tie-breaker.",
            "",
            "Artifacts: `ml/models/fraud_model.joblib`, `ml/models/fraud_preprocessor.joblib`, and `ml/models/metrics.json`.",
        ]
    )
    (output_dir.parent / "evaluation" / "fraud_model_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    dataset_path = obtain_dataset(args.data, args.data_url, root / "ml" / "data" / "raw")
    data = pd.read_csv(dataset_path)
    features, target, details = engineer_features(data)
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=target,
    )
    results = train_models(x_train, y_train, x_test, y_test, args.random_state)
    selected_name = select_model(results)
    write_artifacts(
        results,
        selected_name,
        dataset_path,
        details,
        args.test_size,
        args.random_state,
        root / "ml" / "models",
    )
    print(f"Selected model: {selected_name}")
    for name, value in results.items():
        print(f"{name}: {json.dumps(value['metrics'])}")


if __name__ == "__main__":
    main()
