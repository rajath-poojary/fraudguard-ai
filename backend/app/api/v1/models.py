from __future__ import annotations

import json
from pathlib import Path

import joblib
from fastapi import APIRouter
from fastapi import Depends

from app.core.security import require_permission
from app.models import User
from app.schemas.model_lab import ModelComparison, ModelLabResponse

router = APIRouter(prefix="/models", tags=["model-lab"])


def _model_root() -> Path:
    module_path = Path(__file__).resolve()
    roots = (module_path.parents[3], module_path.parents[4])
    for root in roots:
        model_root = root / "ml" / "models"
        if model_root.is_dir():
            return model_root
    return roots[0] / "ml" / "models"


@router.get("/active/metrics", response_model=ModelLabResponse)
def active_metrics(_: User = Depends(require_permission("model_read"))) -> ModelLabResponse:
    model_root = _model_root()
    metrics_path = model_root / "metrics.json"
    version_path = model_root / "model_version.json"
    if not metrics_path.exists() or not version_path.exists():
        return ModelLabResponse(available=False, health={"data_drift": None, "prediction_drift": None, "performance_change": None})
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    version = json.loads(version_path.read_text(encoding="utf-8"))
    selected_name = str(metrics.get("selected_model") or version.get("selected_model") or "")
    selected = metrics.get("models", {}).get(selected_name, {})
    feature_importance: list[dict[str, float | str]] = []
    classifier_path = model_root / "fraud_model.joblib"
    if classifier_path.exists():
        try:
            pipeline = joblib.load(classifier_path)
            classifier = pipeline.named_steps.get("classifier")
            names = list(pipeline.named_steps["preprocessor"].get_feature_names_out())
            values = list(getattr(classifier, "feature_importances_", []))
            feature_importance = [{"name": name.split("__", 1)[-1], "value": round(float(value), 8)} for name, value in sorted(zip(names, values), key=lambda pair: pair[1], reverse=True)]
        except (AttributeError, KeyError, OSError, ValueError):
            feature_importance = []
    comparisons = [ModelComparison(name=name, model_version=version.get("model_version") if name == selected_name else None, **{key: value for key, value in model_metrics.items() if key in {"precision", "recall", "f1", "roc_auc", "pr_auc", "threshold"}}) for name, model_metrics in metrics.get("models", {}).items()]
    return ModelLabResponse(
        available=True,
        current_model=selected_name or None,
        model_version=version.get("model_version") or metrics.get("model_version"),
        training_dataset=metrics.get("dataset", {}),
        training_timestamp=version.get("training_timestamp"),
        metrics={key: selected.get(key) for key in ("precision", "recall", "f1", "roc_auc", "pr_auc")},
        confusion_matrix=selected.get("confusion_matrix"),
        roc_curve=[{"x": point["fpr"], "y": point["tpr"]} for point in selected.get("roc_curve", [])],
        precision_recall_curve=[{"x": point["recall"], "y": point["precision"]} for point in selected.get("precision_recall_curve", [])],
        feature_importance=feature_importance,
        prediction_distribution=selected.get("prediction_distribution", []),
        risk_distribution=selected.get("risk_distribution", []),
        model_comparison=comparisons,
        historical_versions=metrics.get("historical_versions", []),
        health=metrics.get("health", {"data_drift": None, "prediction_drift": None, "performance_change": None}),
    )