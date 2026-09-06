from math import isfinite

from pydantic import BaseModel, Field, field_validator


class PredictionRequest(BaseModel):
    features: dict[str, float] = Field(min_length=1)

    @field_validator("features")
    @classmethod
    def validate_features(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not isfinite(number) for number in value.values()):
            raise ValueError("features must contain only finite numeric values")
        return value


class PredictionResponse(BaseModel):
    fraud_probability: float = Field(ge=0, le=1)
    model_version: str
    decision: str
    risk_level: str
    anomaly_score: float = Field(ge=0, le=1)
    anomaly_level: str
    top_anomaly_features: list[dict[str, float | str]]
    top_contributing_factors: list[dict[str, float | str]] | None = None
    lower_risk_signals: list[dict[str, float | str]] | None = None
    explanation: dict[str, object] | None = None
