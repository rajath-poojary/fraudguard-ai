from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Device, FraudAlert, RiskEvent, Transaction, User
from app.schemas.transactions import TransactionCreate
from app.services.risk_engine import RiskAssessment, RiskEngine, RiskSignals


class TransactionProcessor:
    def __init__(self, risk_engine: RiskEngine) -> None:
        self.risk_engine = risk_engine

    def process(self, db: Session, user: User, payload: TransactionCreate, model_features: Any) -> tuple[Transaction, RiskAssessment]:
        device_novelty = self._device_novelty(db, user.id, payload.device_fingerprint)
        transaction_frequency = self._frequency(db, user.id, payload.occurred_at)
        transaction = Transaction(
            user_id=user.id,
            merchant_id=payload.merchant_id,
            device_id=payload.device_id,
            amount=payload.amount,
            currency=payload.currency,
            occurred_at=payload.occurred_at,
            metadata_json={
                **payload.metadata,
                "location": payload.location,
                "merchant": payload.merchant,
                "device_status": payload.device_status,
            },
        )
        db.add(transaction)
        db.flush()
        signals = RiskSignals(
            ml_fraud_probability=0.0,
            anomaly_score=0.0,
            transaction_amount_anomaly=float(payload.metadata.get(
                "transaction_amount_anomaly",
                1.0 if payload.amount >= 50000 else 0.0,
            )),
            transaction_frequency=transaction_frequency,
            device_novelty=1.0 if payload.device_status == "new" else device_novelty,
            location_anomaly=float(payload.metadata.get(
                "location_anomaly",
                0.0 if payload.location else 0.25,
            )),
            transaction_time_anomaly=float(payload.metadata.get(
                "transaction_time_anomaly",
                1.0 if payload.occurred_at.hour < 6 else 0.0,
            )),
        )
        assessment = self.risk_engine.assess_with_features(
            transaction={**payload.metadata, "amount": float(payload.amount)},
            model_features=model_features,
            auxiliary_signals=signals,
        )
        transaction.fraud_probability = assessment.signals.ml_fraud_probability
        transaction.anomaly_score = assessment.signals.anomaly_score
        transaction.risk_score = assessment.risk_score
        transaction.risk_level = assessment.risk_level
        transaction.decision = assessment.decision
        transaction.reasons = list(assessment.reasons)
        if assessment.risk_level in {"MEDIUM", "HIGH"}:
            db.add(FraudAlert(
                transaction_id=transaction.id,
                user_id=user.id,
                risk_score=assessment.risk_score,
                reason_code=assessment.reason_codes[0] if assessment.reason_codes else "RISK_SIGNAL",
            ))
        db.add(RiskEvent(
            transaction_id=transaction.id,
            user_id=user.id,
            event_type="risk_assessment",
            risk_score=assessment.risk_score,
            details={"reasons": assessment.reasons, "reason_codes": assessment.reason_codes},
        ))
        db.commit()
        db.refresh(transaction)
        return transaction, assessment

    @staticmethod
    def _frequency(db: Session, user_id: UUID, occurred_at: datetime) -> float:
        start = occurred_at - timedelta(hours=1)
        return float(db.scalar(select(func.count(Transaction.id)).where(
            Transaction.user_id == user_id,
            Transaction.occurred_at >= start,
            Transaction.occurred_at <= occurred_at,
        )) or 0)

    @staticmethod
    def _device_novelty(db: Session, user_id: UUID, fingerprint: str | None) -> float:
        if not fingerprint:
            return 0.0
        known = db.scalar(select(Device.id).where(Device.user_id == user_id, Device.fingerprint == fingerprint).limit(1))
        return 0.0 if known else 1.0
