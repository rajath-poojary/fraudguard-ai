from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_model_runtime
from app.schemas.prediction import PredictionRequest, PredictionResponse
from app.services.model_runtime import ModelRuntime

router = APIRouter(prefix="/api", tags=["prediction"])


@router.post("/predict", response_model=PredictionResponse, response_model_exclude_none=True)
def predict(
    payload: PredictionRequest,
    runtime: ModelRuntime = Depends(get_model_runtime),
) -> PredictionResponse:
    try:
        (
            probability,
            decision,
            risk_level,
            anomaly_score,
            anomaly_level,
            top_anomaly_features,
        ) = runtime.predict_intelligence(payload.features)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    explanation = runtime.explain_prediction(payload.features) if hasattr(runtime, "explain_prediction") else None
    return PredictionResponse(
        fraud_probability=probability,
        model_version=runtime.model_version,
        decision=decision,
        risk_level=risk_level,
        anomaly_score=anomaly_score,
        anomaly_level=anomaly_level,
        top_anomaly_features=top_anomaly_features,
        top_contributing_factors=explanation.get("top_contributing_factors") if explanation else None,
        lower_risk_signals=explanation.get("lower_risk_signals") if explanation else None,
        explanation=explanation,
    )
