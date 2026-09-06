from datetime import datetime, timezone
from uuid import UUID, uuid4

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_model_runtime
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import AuditLog, Base, FraudAlert, InvestigationFeedback, Transaction, User
from app.services.risk_engine import RiskEngine


class DeterministicClassifier:
    def predict_proba(self, features):
        return [[0.08, 0.92] for _ in range(len(features))]


class DeterministicAnomalyDetector:
    def anomaly_score(self, features):
        return pd.Series([0.9 for _ in range(len(features))])


class StubRuntime:
    def __init__(self):
        self.risk_engine = RiskEngine(DeterministicClassifier(), DeterministicAnomalyDetector())

    def model_features(self, transaction):
        return pd.DataFrame([[0.0]])


@pytest.fixture
def e2e_context():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = session_factory()
    user = User(id=uuid4(), email="e2e-admin@example.com", password_hash=hash_password("password123"), role="admin", is_active=True)
    db.add(user)
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_model_runtime] = lambda: StubRuntime()
    try:
        yield db, user
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_attack_simulation_to_investigation_decision(e2e_context):
    db, admin = e2e_context
    client = TestClient(app)

    login = client.post("/auth/login", json={"email": admin.email, "password": "password123"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    simulation = client.post(
        "/transactions/attack-simulate",
        json={"attack_type": "account_takeover", "currency": "USD", "base_location": "Bengaluru", "base_amount": 1200},
        headers=headers,
    )
    assert simulation.status_code == 201
    simulation_data = simulation.json()
    assert simulation_data["transactions_generated"] >= 4
    assert simulation_data["fraudulent_transactions"] >= 2
    assert simulation_data["events"]

    transactions = list(db.scalars(select(Transaction).where(Transaction.user_id == admin.id)).all())
    alerts = list(db.scalars(select(FraudAlert).where(FraudAlert.user_id == admin.id)).all())
    assert len(transactions) == simulation_data["transactions_generated"]
    assert alerts

    event_poll = client.get("/events/poll", headers=headers)
    assert event_poll.status_code == 200
    assert any(event["event_type"] == "transaction_analyzed" for event in event_poll.json()["events"])
    assert any(event["event_type"] == "fraud_alert_created" for event in event_poll.json()["events"])

    cases = client.get("/cases", headers=headers)
    assert cases.status_code == 200
    case_id = cases.json()["items"][0]["id"]
    case = client.get(f"/cases/{case_id}", headers=headers)
    assert case.status_code == 200
    assert case.json()["transaction"]["analysis"] is not None
    assert "timeline" in case.json()

    decision = client.post(f"/cases/{case_id}/actions", json={"action_type": "CONFIRM_FRAUD", "note": "E2E confirmed fraud"}, headers=headers)
    assert decision.status_code == 201

    feedback = client.get("/feedback/analytics", headers=headers)
    assert feedback.status_code == 200
    assert feedback.json()["fraud_confirmation_count"] == 1
    assert feedback.json()["evaluation_records"][0]["label"] == "CONFIRMED_FRAUD"

    audit = client.get("/admin/audit-logs", headers=headers)
    assert audit.status_code == 200
    event_types = {item["event_type"] for item in audit.json()["items"]}
    assert {"login", "decision_override"}.issubset(event_types)
    assert db.scalar(select(InvestigationFeedback).where(InvestigationFeedback.case_id == UUID(case_id))) is not None
    assert db.scalar(select(AuditLog).where(AuditLog.event_type == "decision_override")) is not None


def test_non_admin_cannot_access_control_plane(e2e_context):
    db, _ = e2e_context
    investigator = User(id=uuid4(), email="investigator@example.com", password_hash=hash_password("password123"), role="INVESTIGATOR", is_active=True)
    db.add(investigator)
    db.commit()
    token = create_access_token(investigator.id, investigator.role)
    response = TestClient(app).get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403