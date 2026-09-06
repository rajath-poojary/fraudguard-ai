"""Train and evaluate fraud classifiers on a public transaction dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_curve as sklearn_roc_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier

SEED = 42
MODEL_VERSION = "fraud-classifier-v1.0.0"
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
    parser.add_argument("--model-version", default=MODEL_VERSION)
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


def choose_threshold(y_validation: pd.Series, probabilities: Any) -> float:
    """Choose a recall-weighted F2 operating point from validation predictions."""
    precision, recall, thresholds = precision_recall_curve(y_validation, probabilities)
    if len(thresholds) == 0:
        return 0.5
    f2 = (5 * precision[:-1] * recall[:-1]) / (4 * precision[:-1] + recall[:-1] + 1e-12)
    best = max(range(len(thresholds)), key=lambda index: (f2[index], recall[index], precision[index]))
    return float(thresholds[best])


def evaluate_model(
    model: Pipeline,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    threshold: float,
) -> dict[str, Any]:
    probabilities = model.predict_proba(x_test)[:, 1]
    predictions = (probabilities >= threshold).astype(int)
    matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
    false_positive_rate, true_positive_rate, _ = sklearn_roc_curve(y_test, probabilities)
    curve_precision, curve_recall, _ = precision_recall_curve(y_test, probabilities)
    prediction_bins = [{"key": f"{start:.1f}-{start + 0.1:.1f}", "count": int(((probabilities >= start) & (probabilities < start + 0.1)).sum())} for start in [index / 10 for index in range(10)]]
    prediction_bins[-1]["count"] += int((probabilities >= 1.0).sum())
    return {
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "pr_auc": float(average_precision_score(y_test, probabilities)),
        "threshold": threshold,
        "confusion_matrix": matrix.tolist(),
        "roc_curve": [{"fpr": float(x), "tpr": float(y)} for x, y in zip(false_positive_rate, true_positive_rate)],
        "precision_recall_curve": [{"precision": float(x), "recall": float(y)} for x, y in zip(curve_precision, curve_recall)],
        "prediction_distribution": prediction_bins,
        "risk_distribution": [
            {"key": "LOW", "count": int((predictions == 0).sum())},
            {"key": "HIGH", "count": int((predictions == 1).sum())},
        ],
    }


def train_models(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_validation: pd.DataFrame,
    y_validation: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    random_state: int,
) -> dict[str, dict[str, Any]]:
    try:
        from lightgbm import LGBMClassifier
    except ImportError:
        model_factories = {
            "random_forest": lambda: RandomForestClassifier(
                class_weight="balanced_subsample",
                n_estimators=300,
                n_jobs=-1,
                random_state=random_state,
            )
        }
    else:
        model_factories = {
            "lightgbm": lambda: LGBMClassifier(
                n_estimators=300,
                learning_rate=0.05,
                num_leaves=31,
                class_weight="balanced",
                random_state=random_state,
                verbosity=-1,
            )
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
        validation_probabilities = pipeline.predict_proba(x_validation)[:, 1]
        threshold = choose_threshold(y_validation, validation_probabilities)
        results[name] = {
            "metrics": evaluate_model(pipeline, x_test, y_test, threshold),
            "validation_pr_auc": float(average_precision_score(y_validation, validation_probabilities)),
            "threshold": threshold,
            "pipeline": pipeline,
        }
    return results


def select_model(results: dict[str, dict[str, Any]]) -> str:
    return max(
        results,
        key=lambda name: (
            results[name]["metrics"]["f1"],
            results[name]["metrics"]["recall"],
            results[name]["metrics"]["pr_auc"],
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
    split_details: dict[str, Any],
    model_version: str,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_pipeline: Pipeline = results[selected_name]["pipeline"]
    joblib.dump(selected_pipeline, output_dir / "fraud_model.joblib")
    joblib.dump(selected_pipeline.named_steps["preprocessor"], output_dir / "fraud_preprocessor.joblib")
    (output_dir / "model_version.json").write_text(
        json.dumps(
            {
                "model_name": "fraud-classifier",
                "model_version": model_version,
                "selected_model": selected_name,
                "decision_threshold": results[selected_name]["threshold"],
                "feature_names": list(selected_pipeline.named_steps["preprocessor"].feature_names_in_),
                "training_timestamp": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = {
        "dataset": {
            **dataset_details,
            "path": str(dataset_path),
            "sha256": sha256_file(dataset_path),
        },
        "split": {**split_details, "random_state": random_state, "temporal": True},
        "selection_rule": "highest test F1 at a validation-selected recall-weighted threshold",
        "selected_model": selected_name,
        "model_version": model_version,
        "decision_threshold": results[selected_name]["threshold"],
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
        "| Model | Precision | Recall | F1 | ROC-AUC | PR-AUC | Threshold | Confusion matrix [TN, FP; FN, TP] |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, value in results.items():
        metric = value["metrics"]
        report.append(
            f"| {name} | {metric['precision']:.6f} | {metric['recall']:.6f} | {metric['f1']:.6f} | {metric['roc_auc']:.6f} | {metric['pr_auc']:.6f} | {metric['threshold']:.6f} | {metric['confusion_matrix']} |"
        )
    report.extend(
        [
            "",
            f"## Selected model",
            "",
            f"`{selected_name}` uses model version `{model_version}`. Its operating threshold ({results[selected_name]['threshold']:.6f}) was selected only from validation data using recall-weighted F2, avoiding an arbitrary 0.5 cutoff.",
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
    if "Time" in data.columns:
        data = data.sort_values("Time", kind="mergesort").reset_index(drop=True)
    features, target, details = engineer_features(data)
    if not 0 < args.test_size < 0.5:
        raise TrainingError("test-size must be greater than 0 and less than 0.5")
    train_end = int(len(features) * (1 - 2 * args.test_size))
    validation_end = int(len(features) * (1 - args.test_size))
    x_train, x_validation, x_test = (
        features.iloc[:train_end], features.iloc[train_end:validation_end], features.iloc[validation_end:]
    )
    y_train, y_validation, y_test = (
        target.iloc[:train_end], target.iloc[train_end:validation_end], target.iloc[validation_end:]
    )
    for split_name, split_target in (("train", y_train), ("validation", y_validation), ("test", y_test)):
        if split_target.nunique() < 2:
            raise TrainingError(f"Temporal {split_name} split must contain both classes")
    results = train_models(x_train, y_train, x_validation, y_validation, x_test, y_test, args.random_state)
    selected_name = select_model(results)
    write_artifacts(
        results,
        selected_name,
        dataset_path,
        details,
        args.test_size,
        args.random_state,
        {
            "train_rows": len(x_train),
            "validation_rows": len(x_validation),
            "test_rows": len(x_test),
            "validation_fraction": args.test_size,
            "test_fraction": args.test_size,
        },
        args.model_version,
        root / "ml" / "models",
    )
    print(f"Selected model: {selected_name}")
    for name, value in results.items():
        print(f"{name}: {json.dumps(value['metrics'])}")


if __name__ == "__main__":
    main()
