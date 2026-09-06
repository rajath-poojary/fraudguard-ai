from fastapi.testclient import TestClient

from app.api.dependencies import get_model_runtime
from app.main import app


class StubRuntime:
    model_version = "fraud-classifier-v1.0.0"

    def predict_intelligence(self, features: dict[str, float]) -> tuple[float, str, str, float, str, list[dict[str, float | str]]]:
        assert features == {"amount": 10.0}
        return 0.83, "BLOCK", "HIGH", 0.72, "MEDIUM", [{"feature": "amount_log1p", "deviation": 4.2}]


def test_prediction_contract_returns_probability_and_model_metadata():
    app.dependency_overrides[get_model_runtime] = lambda: StubRuntime()
    try:
        response = TestClient(app).post("/api/predict", json={"features": {"amount": 10}})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "fraud_probability": 0.83,
        "model_version": "fraud-classifier-v1.0.0",
        "decision": "BLOCK",
        "risk_level": "HIGH",
        "anomaly_score": 0.72,
        "anomaly_level": "MEDIUM",
        "top_anomaly_features": [{"feature": "amount_log1p", "deviation": 4.2}],
    }
