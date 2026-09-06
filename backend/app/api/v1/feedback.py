from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import InvestigationCase, InvestigationFeedback, User
from app.schemas.feedback import FeedbackAnalyticsResponse, FeedbackEvaluationRecord, SignalFeedbackMetric

router = APIRouter(prefix="/feedback", tags=["feedback-evaluation"])


@router.get("/analytics", response_model=FeedbackAnalyticsResponse)
def feedback_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackAnalyticsResponse:
    query = select(InvestigationFeedback).join(InvestigationCase, InvestigationCase.id == InvestigationFeedback.case_id).order_by(InvestigationFeedback.created_at.asc())
    if getattr(user, "role", "user") != "admin":
        query = query.where(InvestigationCase.alert.has(user_id=user.id))
    records = list(db.scalars(query).all())
    latest: dict[str, InvestigationFeedback] = {}
    for record in records:
        latest[str(record.case_id)] = record
    reviewed = list(latest.values())
    confirmed = sum(record.label == "CONFIRMED_FRAUD" for record in reviewed)
    false_positive = sum(record.label == "FALSE_POSITIVE" for record in reviewed)
    uncertain = sum(record.label == "UNCERTAIN" for record in reviewed)
    denominator = confirmed + false_positive
    alerts_query = select(InvestigationCase)
    if getattr(user, "role", "user") != "admin":
        alerts_query = alerts_query.where(InvestigationCase.alert.has(user_id=user.id))
    total_cases = len(list(db.scalars(alerts_query).all()))

    signal_reviewed: defaultdict[str, int] = defaultdict(int)
    signal_false_positive: defaultdict[str, int] = defaultdict(int)
    for record in reviewed:
        for signal in set(record.reason_codes or []):
            signal_reviewed[signal] += 1
            if record.label == "FALSE_POSITIVE":
                signal_false_positive[signal] += 1
    signal_metrics = [SignalFeedbackMetric(signal=signal, false_positive_count=signal_false_positive[signal], reviewed_count=count, false_positive_rate=round(signal_false_positive[signal] / count * 100, 2)) for signal, count in sorted(signal_reviewed.items(), key=lambda item: (-signal_false_positive[item[0]], item[0]))]
    evaluation_records = [FeedbackEvaluationRecord(case_id=str(record.case_id), transaction_id=str(record.transaction_id), label=record.label, fraud_probability=float(record.fraud_probability) if record.fraud_probability is not None else None, risk_score=float(record.risk_score) if record.risk_score is not None else None, reason_codes=record.reason_codes or [], created_at=record.created_at.isoformat()) for record in reviewed]
    return FeedbackAnalyticsResponse(
        false_positive_count=false_positive,
        false_positive_rate=round(false_positive / denominator * 100, 2) if denominator else 0.0,
        fraud_confirmation_count=confirmed,
        fraud_confirmation_rate=round(confirmed / len(reviewed) * 100, 2) if reviewed else 0.0,
        uncertain_count=uncertain,
        reviewed_count=len(reviewed),
        review_rate=round(len(reviewed) / total_cases * 100, 2) if total_cases else 0.0,
        signal_metrics=signal_metrics,
        evaluation_records=evaluation_records,
    )