from typing import Any

from pydantic import BaseModel, Field


class CurvePoint(BaseModel):
    x: float
    y: float


class ModelComparison(BaseModel):
    name: str
    model_version: str | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    roc_auc: float | None = None
    pr_auc: float | None = None
    threshold: float | None = None


class ModelLabResponse(BaseModel):
    available: bool
    current_model: str | None = None
    model_version: str | None = None
    training_dataset: dict[str, Any] = Field(default_factory=dict)
    training_timestamp: str | None = None
    metrics: dict[str, float | None] = Field(default_factory=dict)
    confusion_matrix: list[list[int]] | None = None
    roc_curve: list[CurvePoint] = Field(default_factory=list)
    precision_recall_curve: list[CurvePoint] = Field(default_factory=list)
    feature_importance: list[dict[str, float | str]] = Field(default_factory=list)
    prediction_distribution: list[dict[str, float | str]] = Field(default_factory=list)
    risk_distribution: list[dict[str, float | str]] = Field(default_factory=list)
    model_comparison: list[ModelComparison] = Field(default_factory=list)
    historical_versions: list[dict[str, Any]] = Field(default_factory=list)
    health: dict[str, str | None] = Field(default_factory=dict)