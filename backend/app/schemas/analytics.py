from typing import Any

from pydantic import BaseModel, Field


class AnalyticsOverview(BaseModel):
    fraud_trend: list[dict[str, Any]] = Field(default_factory=list)
    risk_distribution: list[dict[str, Any]] = Field(default_factory=list)
    fraud_by_hour: list[dict[str, Any]] = Field(default_factory=list)
    fraud_by_merchant_category: list[dict[str, Any]] = Field(default_factory=list)
    fraud_by_device: list[dict[str, Any]] = Field(default_factory=list)
    fraud_by_location: list[dict[str, Any]] = Field(default_factory=list)
    amount_distribution: list[dict[str, Any]] = Field(default_factory=list)
    detection_performance: dict[str, Any] = Field(default_factory=dict)
    false_positive_trend: list[dict[str, Any]] = Field(default_factory=list)
    financial_exposure: dict[str, Any] = Field(default_factory=dict)
    attack_simulation_performance: list[dict[str, Any]] = Field(default_factory=list)
    network_risk_clusters: list[dict[str, Any]] = Field(default_factory=list)