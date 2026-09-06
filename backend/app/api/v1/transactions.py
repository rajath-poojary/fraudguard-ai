from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_model_runtime
from app.core.database import get_db
from app.core.security import get_current_user
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
            risk_score=float(transaction.risk_score),
            risk_level=transaction.risk_level or "LOW",
            decision=transaction.decision or "APPROVE",
            reasons=transaction.reasons or [],
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
    query = select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.created_at.desc())
    items = list(db.scalars(query.offset(offset).limit(limit)))
    total = db.scalar(select(func.count(Transaction.id)).where(Transaction.user_id == user.id)) or 0
    return TransactionListResponse(items=[to_response(item) for item in items], total=total)


@router.post("/transactions/simulate", response_model=SimulationResponse, status_code=status.HTTP_201_CREATED)
def simulate(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    runtime: ModelRuntime = Depends(get_model_runtime),
) -> SimulationResponse:
    return SimulationResponse(transaction=create_transaction(payload, user, db, runtime))


@router.post("/transactions/attack-simulate", response_model=AttackSimulationResponse, status_code=status.HTTP_201_CREATED)
def attack_simulate(
    payload: AttackSimulationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    runtime: ModelRuntime = Depends(get_model_runtime),
) -> AttackSimulationResponse:
    now = datetime.now(timezone.utc)
    fingerprint = f"attack-{user.id}"
    normal = {
        "amount": payload.base_amount,
        "location": payload.base_location,
        "device_status": "known",
        "merchant": "Everyday Goods",
        "device_fingerprint": fingerprint,
    }
    sequences = {
        "normal": [normal] * 3,
        "account_takeover": [normal, normal, {**normal, "amount": Decimal("75000"), "location": "Mumbai", "device_status": "new"}, {**normal, "amount": Decimal("92000"), "location": "Mumbai", "device_status": "new"}],
        "card_testing": [{**normal, "amount": Decimal("2"), "merchant": "Card Test Merchant", "device_fingerprint": f"test-{user.id}"}] * 6,
        "velocity": [{**normal, "amount": Decimal("45000"), "device_status": "new"}] * 7,
        "impossible_travel": [normal, {**normal, "location": "London", "device_status": "new", "amount": Decimal("72000")}],
        "device_takeover": [normal, normal, {**normal, "device_status": "new", "device_fingerprint": f"takeover-{user.id}", "amount": Decimal("68000")}],
        "fraud_ring": [{**normal, "device_status": "new", "device_fingerprint": f"ring-{index}", "merchant": "High Risk Exchange", "amount": Decimal("52000")} for index in range(6)],
    }
    generated: list[TransactionResponse] = []
    for index, item in enumerate(sequences[payload.attack_type]):
        transaction_payload = TransactionCreate(
            amount=item["amount"], currency=payload.currency,
            occurred_at=now + timedelta(seconds=index * (3 if payload.attack_type == "velocity" else 30)),
            location=item["location"], device_status=item["device_status"],
            merchant=item["merchant"], device_fingerprint=item["device_fingerprint"],
            metadata={"attack_type": payload.attack_type},
        )
        generated.append(create_transaction(transaction_payload, user, db, runtime))
    scores = [float(item.analysis.risk_score) for item in generated if item.analysis]
    detected = [item for item in generated if item.analysis and item.analysis.risk_level in {"MEDIUM", "HIGH"}]
    return AttackSimulationResponse(
        attack_type=payload.attack_type,
        transactions_generated=len(generated),
        detected_transactions=len(detected),
        detection_rate=(len(detected) / len(generated) * 100) if generated else 0,
        peak_risk_score=max(scores, default=0),
        detected=bool(detected),
        transactions=generated,
    )


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransactionResponse:
    transaction = db.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id))
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
    query = select(FraudAlert).where(FraudAlert.user_id == user.id).order_by(FraudAlert.created_at.desc())
    items = list(db.scalars(query.offset(offset).limit(limit)))
    total = db.scalar(select(func.count(FraudAlert.id)).where(FraudAlert.user_id == user.id)) or 0
    return FraudAlertListResponse(items=[FraudAlertResponse.model_validate(item) for item in items], total=total)


@router.get("/fraud-alerts/{alert_id}", response_model=FraudAlertResponse)
def get_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FraudAlertResponse:
    alert = db.scalar(select(FraudAlert).where(FraudAlert.id == alert_id, FraudAlert.user_id == user.id))
    if alert is None:
        raise HTTPException(status_code=404, detail="Fraud alert not found")
    return FraudAlertResponse.model_validate(alert)
