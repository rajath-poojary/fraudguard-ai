from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Device, FraudAlert, RiskEvent, Transaction, User
from app.schemas.transactions import TransactionCreate
from app.services.risk_engine import RiskAssessment, RiskEngine, RiskSignals, RuleEngine, RuleMatch


def _ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class TransactionProcessor:
    def __init__(self, risk_engine: RiskEngine) -> None:
        self.risk_engine = risk_engine

    def process(self, db: Session, user: User, payload: TransactionCreate, model_features: Any) -> tuple[Transaction, RiskAssessment]:
        device_novelty = self._device_novelty(db, user.id, payload.device_fingerprint)
        transaction_frequency = self._frequency(db, user.id, payload.occurred_at)
        prior = self._prior_transaction(db, user.id)
        prior_metadata = prior.metadata_json if prior else {}
        prior_location = prior_metadata.get("location") if prior_metadata else None
        impossible_travel = bool(
            prior_location
            and payload.location
            and prior_location != payload.location
            and prior
            and _ensure_utc(payload.occurred_at) - _ensure_utc(prior.occurred_at) <= timedelta(minutes=15)
        )
        behavior_deviation = self._behavior_deviation(db, user.id, float(payload.amount), payload.location)
        network_evidence = self._network_evidence(db, payload.device_id, payload.device_fingerprint, payload.ip_address)
        device_intelligence = max(
            1.0 if payload.device_status == "new" else device_novelty,
            self._device_intelligence(db, payload.device_id),
        )
        merchant_intelligence = self._merchant_intelligence(db, payload.merchant_id, payload.merchant_category)
        occurred_time = payload.timestamp or payload.occurred_at
        prev_tx_id = payload.previous_transaction_id or (prior.id if prior else None)
        calculated_account_age = payload.account_age
        if calculated_account_age is None and hasattr(user, "created_at") and user.created_at:
            calculated_account_age = max(0, (occurred_time.date() - user.created_at.date()).days)

        transaction = Transaction(
            user_id=user.id,
            merchant_id=payload.merchant_id,
            device_id=payload.device_id,
            amount=payload.amount,
            currency=payload.currency,
            status=payload.transaction_status or "pending",
            occurred_at=occurred_time,
            merchant_category=payload.merchant_category,
            ip_address=payload.ip_address,
            location=payload.location,
            account_age=calculated_account_age,
            payment_method=payload.payment_method,
            previous_transaction_id=prev_tx_id,
            is_fraud=payload.is_fraud,
            fraud_scenario=payload.fraud_scenario,
            metadata_json={
                **payload.metadata,
                "location": payload.location,
                "merchant": payload.merchant,
                "device_status": payload.device_status,
                "ip_address": payload.ip_address,
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
            behavior_deviation=behavior_deviation,
            temporal_evidence=min(transaction_frequency / 5.0, 1.0),
            network_evidence=network_evidence,
            merchant_intelligence=merchant_intelligence,
            device_intelligence=device_intelligence,
        )
        assessment = self.risk_engine.assess_with_features(
            transaction={
                **payload.metadata,
                "amount": float(payload.amount),
                "device_status": payload.device_status,
                "location": payload.location,
                "merchant": payload.merchant,
                "transaction_frequency": transaction_frequency,
                "prior_location": prior_location,
                "impossible_travel": impossible_travel,
                "behavior_deviation": behavior_deviation,
            },
            model_features=model_features,
            auxiliary_signals=signals,
        )
        transaction.fraud_probability = assessment.fraud_probability
        transaction.anomaly_score = assessment.signals.anomaly_score
        transaction.risk_score = assessment.risk_score
        transaction.risk_level = assessment.risk_level
        transaction.decision = assessment.decision
        transaction.reasons = list(assessment.reasons)
        transaction.metadata_json = {
            **(transaction.metadata_json or {}),
            "contributions": [vars(item) for item in assessment.contributions],
            "rule_matches": [vars(item) for item in assessment.rule_matches],
            "evidence": [item.explanation for item in assessment.evidence],
            "reason_codes": list(assessment.reason_codes),
            "explanation": assessment.explanation,
        }
        self._record_device(db, user.id, payload)
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

    @staticmethod
    def _prior_transaction(db: Session, user_id: UUID) -> Transaction | None:
        return db.scalar(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.occurred_at.desc())
            .limit(1)
        )

    @staticmethod
    def _behavior_deviation(db: Session, user_id: UUID, amount: float, location: str | None) -> float:
        recent = list(db.scalars(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.occurred_at.desc())
            .limit(20)
        ))
        if not recent:
            return 0.0
        average_amount = sum(float(item.amount) for item in recent) / len(recent)
        amount_deviation = 1.0 if average_amount and amount > average_amount * 5 else 0.0
        known_locations = {(
            item.metadata_json or {}
        ).get("location") for item in recent}
        location_deviation = 1.0 if location and known_locations and location not in known_locations else 0.0
        return max(amount_deviation, location_deviation)

    @staticmethod
    def _network_evidence(db: Session, device_id: UUID | None, device_fingerprint: str | None, ip_address: str | None) -> float:
        shared_device_users = {
            item for item in db.scalars(select(Transaction.user_id).where(Transaction.device_id == device_id)).all()
        } if device_id else set()
        shared_ip_users = {
            item for item in db.scalars(select(Transaction.user_id).where(Transaction.ip_address == ip_address)).all()
        } if ip_address else set()
        repeated_fingerprint = db.scalar(select(func.count(Device.id)).where(Device.fingerprint == device_fingerprint)) if device_fingerprint else 0
        return min(1.0, max((len(shared_device_users) - 1) / 3.0, (len(shared_ip_users) - 1) / 3.0, float(repeated_fingerprint or 0) / 3.0, 0.0))

    @staticmethod
    def _device_intelligence(db: Session, device_id: UUID | None) -> float:
        if not device_id:
            return 0.0
        users = set(db.scalars(select(Transaction.user_id).where(Transaction.device_id == device_id)).all())
        return min(1.0, max(0, len(users) - 1) / 3.0)

    @staticmethod
    def _merchant_intelligence(db: Session, merchant_id: UUID | None, merchant_category: str | None) -> float:
        if merchant_id:
            history = list(db.scalars(select(Transaction).where(Transaction.merchant_id == merchant_id)).all())
        elif merchant_category:
            history = list(db.scalars(select(Transaction).where(Transaction.merchant_category == merchant_category)).all())
        else:
            return 0.0
        if not history:
            return 0.0
        suspicious = sum(
            item.is_fraud or item.decision in {"REVIEW", "BLOCK"} or item.risk_level in {"MEDIUM", "HIGH"}
            for item in history
        )
        return min(1.0, suspicious / len(history))

    @staticmethod
    def _record_device(db: Session, user_id: UUID, payload: TransactionCreate) -> None:
        if not payload.device_fingerprint:
            return
        device = db.scalar(select(Device).where(
            Device.user_id == user_id,
            Device.fingerprint == payload.device_fingerprint,
        ))
        now = datetime.now(timezone.utc)
        if device is None:
            db.add(Device(
                user_id=user_id,
                fingerprint=payload.device_fingerprint,
                first_seen_at=now,
                last_seen_at=now,
            ))
        else:
            device.last_seen_at = now
