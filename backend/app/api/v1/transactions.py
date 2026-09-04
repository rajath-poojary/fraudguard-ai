from datetime import datetime, timezone
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
        )
    return TransactionResponse(
        id=transaction.id,
        user_id=transaction.user_id,
        amount=transaction.amount,
        currency=transaction.currency,
        status=transaction.status,
        occurred_at=transaction.occurred_at,
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
