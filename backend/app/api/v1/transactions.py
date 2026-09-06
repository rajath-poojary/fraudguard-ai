from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_model_runtime
from app.core.database import get_db
from app.core.security import canonical_role, get_current_user
from app.models import FraudAlert, Transaction, User
from app.schemas.transactions import (
    FraudAlertListResponse,
    FraudAlertResponse,
    SimulationResponse,
    AttackSimulationRequest,
    AttackSimulationResponse,
    TransactionAnalysis,
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
)
from app.services.model_runtime import ModelRuntime
from app.services.transaction_processor import TransactionProcessor

router = APIRouter(tags=["transactions"])


def to_response(transaction: Transaction) -> TransactionResponse:
    analysis = None
    if transaction.risk_score is not None:
        analysis = TransactionAnalysis(
            fraud_probability=float(transaction.fraud_probability or 0),
            anomaly_score=float(transaction.anomaly_score or 0),
            expected_loss=float((transaction.metadata_json or {}).get("explanation", {}).get("expected_loss", 0)),
            risk_score=float(transaction.risk_score),
            risk_level=transaction.risk_level or "LOW",
            decision=transaction.decision or "APPROVE",
            reasons=transaction.reasons or [],
            evidence=(transaction.metadata_json or {}).get("evidence", []),
            reason_codes=(transaction.metadata_json or {}).get("reason_codes", []),
            explanation=(transaction.metadata_json or {}).get("explanation", {}),
            contributions=(transaction.metadata_json or {}).get("contributions", []),
            rule_matches=(transaction.metadata_json or {}).get("rule_matches", []),
        )
    return TransactionResponse(
        id=transaction.id,
        transaction_id=transaction.id,
        user_id=transaction.user_id,
        amount=transaction.amount,
        currency=transaction.currency,
        status=transaction.status,
        transaction_status=transaction.status,
        occurred_at=transaction.occurred_at,
        timestamp=transaction.occurred_at,
        merchant_id=transaction.merchant_id,
        merchant_category=transaction.merchant_category,
        device_id=transaction.device_id,
        ip_address=transaction.ip_address,
        location=transaction.location,
        account_age=transaction.account_age,
        payment_method=transaction.payment_method,
        previous_transaction_id=transaction.previous_transaction_id,
        is_fraud=transaction.is_fraud,
        fraud_scenario=transaction.fraud_scenario,
        analysis=analysis,
        created_at=transaction.created_at,
    )


def create_transaction(
    payload: TransactionCreate,
    user: User,
    db: Session,
    runtime: ModelRuntime,
) -> TransactionResponse:
    transaction_data = {
        "amount": float(payload.amount),
        "Amount": float(payload.amount),
        "occurred_at": payload.occurred_at,
        **payload.metadata,
    }
    processor = TransactionProcessor(runtime.risk_engine)
    transaction, _ = processor.process(db, user, payload, runtime.model_features(transaction_data))
    return to_response(transaction)


@router.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    runtime: ModelRuntime = Depends(get_model_runtime),
) -> TransactionResponse:
    return create_transaction(payload, user, db, runtime)


@router.get("/transactions", response_model=TransactionListResponse)
def list_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransactionListResponse:
    is_admin = canonical_role(user.role) == "ADMIN"
    scope = True if is_admin else (Transaction.user_id == user.id)
    query = select(Transaction).where(scope).order_by(Transaction.created_at.desc())
    items = list(db.scalars(query.offset(offset).limit(limit)))
    total = db.scalar(select(func.count(Transaction.id)).where(scope)) or 0
    return TransactionListResponse(items=[to_response(item) for item in items], total=total)


@router.post("/transactions/simulate", response_model=SimulationResponse, status_code=status.HTTP_201_CREATED)
def simulate(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    runtime: ModelRuntime = Depends(get_model_runtime),
) -> SimulationResponse:
    return SimulationResponse(transaction=create_transaction(payload, user, db, runtime))


def _simulation_steps(attack_type: str, base_amount: Decimal, location: str, fingerprint: str) -> list[dict]:
    baseline = {
        "amount": base_amount,
        "location": location,
        "device_status": "known",
        "merchant": "Everyday Goods",
        "device_fingerprint": fingerprint,
        "ip_address": "203.0.113.10",
        "is_fraud": False,
    }

    def transaction(label: str, offset: int, *, amount: Decimal | None = None, fraud: bool = True, **changes: object) -> dict:
        return {
            "kind": "transaction",
            "label": label,
            "offset_seconds": offset,
            **baseline,
            "amount": amount or base_amount,
            "is_fraud": fraud,
            **changes,
        }

    def event(label: str, offset: int, event_type: str) -> dict:
        return {"kind": "event", "label": label, "offset_seconds": offset, "event_type": event_type}

    if attack_type == "normal":
        return [
            transaction("Normal activity", 0, fraud=False),
            transaction("Normal activity", 45, fraud=False),
            transaction("Normal activity", 120, fraud=False),
            transaction("Normal activity", 240, fraud=False),
        ]
    if attack_type == "account_takeover":
        return [
            transaction("Normal activity", 0, fraud=False),
            transaction("New device", 15, amount=base_amount, device_status="new", device_fingerprint=f"new-{fingerprint}"),
            event("Login anomaly", 30, "authentication_anomaly"),
            transaction("Large transaction", 42, amount=Decimal("50000"), location="Mumbai", device_status="new", device_fingerprint=f"new-{fingerprint}"),
            transaction("Second large transaction", 45, amount=Decimal("75000"), location="Mumbai", device_status="new", device_fingerprint=f"new-{fingerprint}"),
            event("Transaction burst", 47, "velocity_anomaly"),
        ]
    if attack_type == "card_testing":
        return [
            transaction("Card verification", 0, amount=Decimal("1.00")),
            transaction("Micro-authorization", 12, amount=Decimal("2.00"), fraud=True, merchant="Card Test Merchant"),
            transaction("Micro-authorization", 24, amount=Decimal("0.99"), fraud=True, merchant="Card Test Merchant"),
            transaction("Micro-authorization", 38, amount=Decimal("1.50"), fraud=True, merchant="Card Test Merchant"),
            transaction("Failed authorization", 51, amount=Decimal("2.25"), fraud=True, merchant="Card Test Merchant", transaction_status="failed"),
            transaction("Card drain attempt", 68, amount=Decimal("18000"), fraud=True, merchant="Card Test Merchant"),
        ]
    if attack_type == "velocity":
        return [
            transaction("Normal activity", 0, fraud=False),
            transaction("Rapid payment 1", 10, amount=Decimal("45000")),
            transaction("Rapid payment 2", 20, amount=Decimal("45000")),
            transaction("Rapid payment 3", 30, amount=Decimal("45000")),
            transaction("Rapid payment 4", 40, amount=Decimal("45000")),
            transaction("Rapid payment 5", 50, amount=Decimal("45000")),
            event("Transaction burst", 52, "velocity_anomaly"),
        ]
    if attack_type == "device_takeover":
        return [
            transaction("Normal activity", 0, fraud=False),
            transaction("New device fingerprint", 20, device_status="new", device_fingerprint=f"takeover-{fingerprint}"),
            event("Device risk signal", 26, "device_anomaly"),
            transaction("Unauthorized purchase", 38, amount=Decimal("68000"), device_status="new", device_fingerprint=f"takeover-{fingerprint}"),
            transaction("Second unauthorized purchase", 55, amount=Decimal("42000"), device_status="new", device_fingerprint=f"takeover-{fingerprint}"),
        ]
    if attack_type == "impossible_travel":
        return [
            transaction("Normal activity", 0, fraud=False),
            transaction("Distant location", 20, amount=Decimal("4200"), location="London", device_status="new", device_fingerprint=f"remote-{fingerprint}", ip_address="198.51.100.20"),
            event("Impossible travel detected", 21, "geo_velocity_anomaly"),
            transaction("Remote follow-up purchase", 35, amount=Decimal("12000"), location="London", device_status="new", device_fingerprint=f"remote-{fingerprint}", ip_address="198.51.100.20"),
        ]
    if attack_type in {"coordinated_fraud", "fraud_ring"}:
        return [
            transaction("Normal activity", 0, fraud=False),
            transaction("Shared device association 1", 30, amount=Decimal("900"), device_status="new", device_fingerprint="ring-shared-device", ip_address="192.0.2.199"),
            transaction("Shared device association 2", 75, amount=Decimal("1100"), device_status="new", device_fingerprint="ring-shared-device", ip_address="192.0.2.199"),
            transaction("Coordinated purchase 1", 120, amount=Decimal("2400"), device_status="new", device_fingerprint="ring-shared-device", ip_address="192.0.2.199"),
            transaction("Coordinated purchase 2", 165, amount=Decimal("3200"), device_status="new", device_fingerprint="ring-shared-device", ip_address="192.0.2.199"),
            event("Network association detected", 170, "network_association"),
        ]
    if attack_type == "merchant_abuse":
        return [
            transaction("Normal activity", 0, fraud=False),
            transaction("High-risk merchant purchase 1", 45, amount=Decimal("5000"), merchant="High Risk Exchange", merchant_category="crypto"),
            transaction("High-risk merchant purchase 2", 180, amount=Decimal("7500"), merchant="High Risk Exchange", merchant_category="crypto"),
            transaction("High-risk merchant purchase 3", 330, amount=Decimal("10000"), merchant="High Risk Exchange", merchant_category="crypto"),
            event("Merchant abuse pattern detected", 340, "merchant_pattern"),
        ]
    raise HTTPException(status_code=422, detail=f"Unsupported attack type: {attack_type}")


@router.post("/transactions/attack-simulate", response_model=AttackSimulationResponse, status_code=status.HTTP_201_CREATED)
def attack_simulate(
    payload: AttackSimulationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    runtime: ModelRuntime = Depends(get_model_runtime),
) -> AttackSimulationResponse:
    now = datetime.now(timezone.utc)
    fingerprint = f"attack-{user.id}"
    attack_type = "coordinated_fraud" if payload.attack_type == "fraud_ring" else payload.attack_type
    steps = _simulation_steps(attack_type, payload.base_amount, payload.base_location, fingerprint)
    generated: list[TransactionResponse] = []
    events: list[dict] = []
    for index, item in enumerate(steps):
        if item["kind"] == "event":
            events.append({
                "event_id": f"event-{index + 1}", "offset_seconds": item["offset_seconds"],
                    "label": item["label"], "event_type": item["event_type"], "detected": False, "signals": [item["label"]],
            })
            continue
        transaction_payload = TransactionCreate(
            amount=item["amount"], currency=payload.currency,
            occurred_at=now + timedelta(seconds=item["offset_seconds"]),
            location=item["location"], device_status=item["device_status"],
            merchant=item["merchant"], device_fingerprint=item["device_fingerprint"], ip_address=item["ip_address"],
            merchant_category=item.get("merchant_category"), transaction_status=item.get("transaction_status", "pending"),
            is_fraud=item["is_fraud"], fraud_scenario=attack_type,
            metadata={"attack_type": attack_type, "simulation_label": item["label"]},
        )
        response = create_transaction(transaction_payload, user, db, runtime)
        generated.append(response)
        analysis = response.analysis
        events.append({
            "event_id": f"event-{index + 1}", "offset_seconds": item["offset_seconds"], "label": item["label"],
            "event_type": "transaction", "transaction_id": response.id, "amount": float(response.amount),
            "risk_score": analysis.risk_score if analysis else None, "fraud_probability": analysis.fraud_probability if analysis else None,
            "decision": analysis.decision if analysis else None, "risk_level": analysis.risk_level if analysis else None,
            "detected": bool(response.is_fraud and analysis and analysis.decision in {"REVIEW", "BLOCK"}),
            "signals": analysis.reason_codes if analysis else [],
        })
    scores = [float(item.analysis.risk_score) for item in generated if item.analysis]
    fraudulent = [item for item in generated if item.is_fraud]
    detected = [item for item in fraudulent if item.analysis and item.analysis.decision in {"REVIEW", "BLOCK"}]
    blocked = [item for item in generated if item.analysis and item.analysis.decision == "BLOCK"]
    reviewed = [item for item in generated if item.analysis and item.analysis.decision == "REVIEW"]
    detection_offsets = [event["offset_seconds"] for event in events if event["detected"]]
    exposure = sum(float(item.amount) for item in fraudulent)
    prevented = sum(float(item.amount) for item in fraudulent if item.analysis and item.analysis.decision == "BLOCK")
    return AttackSimulationResponse(
        attack_type=attack_type,
        transactions_generated=len(generated),
        fraudulent_transactions=len(fraudulent),
        detected_transactions=len(detected),
        missed_transactions=max(0, len(fraudulent) - len(detected)),
        blocked_transactions=len(blocked),
        reviewed_transactions=len(reviewed),
        detection_rate=(len(detected) / len(fraudulent) * 100) if fraudulent else 0,
        peak_risk_score=max(scores, default=0),
        detected=bool(detected),
        detection_time_seconds=min(detection_offsets) if detection_offsets else None,
        average_detection_time_seconds=(sum(detection_offsets) / len(detection_offsets)) if detection_offsets else None,
        financial_exposure=exposure,
        financial_exposure_prevented=prevented,
        events=events,
        transactions=generated,
    )


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransactionResponse:
    scope = True if canonical_role(user.role) == "ADMIN" else (Transaction.user_id == user.id)
    transaction = db.scalar(select(Transaction).where(Transaction.id == transaction_id, scope))
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return to_response(transaction)


@router.get("/fraud-alerts", response_model=FraudAlertListResponse)
def list_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FraudAlertListResponse:
    scope = True if canonical_role(user.role) == "ADMIN" else (FraudAlert.user_id == user.id)
    query = select(FraudAlert).where(scope).order_by(FraudAlert.created_at.desc())
    items = list(db.scalars(query.offset(offset).limit(limit)))
    total = db.scalar(select(func.count(FraudAlert.id)).where(scope)) or 0
    return FraudAlertListResponse(items=[FraudAlertResponse.model_validate(item) for item in items], total=total)


@router.get("/fraud-alerts/{alert_id}", response_model=FraudAlertResponse)
def get_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FraudAlertResponse:
    scope = True if canonical_role(user.role) == "ADMIN" else (FraudAlert.user_id == user.id)
    alert = db.scalar(select(FraudAlert).where(FraudAlert.id == alert_id, scope))
    if alert is None:
        raise HTTPException(status_code=404, detail="Fraud alert not found")
    return FraudAlertResponse.model_validate(alert)
