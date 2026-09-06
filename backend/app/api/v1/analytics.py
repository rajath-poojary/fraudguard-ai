from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import canonical_role, require_permission
from app.models import Device, InvestigationCase, InvestigationFeedback, Transaction, User
from app.schemas.analytics import AnalyticsOverview
from app.services.network_intelligence import NetworkIntelligence

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _fraud(transaction: Transaction) -> bool:
    return bool(transaction.is_fraud)


def _detected(transaction: Transaction) -> bool:
    return transaction.decision in {"REVIEW", "BLOCK"}


def _grouped(rows: list[Transaction], key, limit: int = 12) -> list[dict[str, object]]:
    counts: Counter[str] = Counter()
    frauds: Counter[str] = Counter()
    for row in rows:
        value = str(key(row) or "Unknown")
        counts[value] += 1
        if _fraud(row):
            frauds[value] += 1
    return [{"label": label, "transactions": count, "fraud_transactions": frauds[label], "fraud_rate": round(frauds[label] / count * 100, 2) if count else 0.0} for label, count in counts.most_common(limit)]


@router.get("/overview", response_model=AnalyticsOverview)
def overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics_read")),
) -> AnalyticsOverview:
    query = select(Transaction).options(selectinload(Transaction.merchant), selectinload(Transaction.device)).order_by(Transaction.occurred_at.asc())
    if canonical_role(getattr(user, "role", "")) != "ADMIN":
        query = query.where(Transaction.user_id == user.id)
    transactions = list(db.scalars(query).all())
    fraud_transactions = [row for row in transactions if _fraud(row)]

    by_day: defaultdict[str, dict[str, float]] = defaultdict(lambda: {"transactions": 0, "fraud_transactions": 0, "fraud_amount": 0.0})
    for row in transactions:
        key = row.occurred_at.date().isoformat()
        by_day[key]["transactions"] += 1
        if _fraud(row):
            by_day[key]["fraud_transactions"] += 1
            by_day[key]["fraud_amount"] += float(row.amount)
    fraud_trend = [{"label": key, **value} for key, value in sorted(by_day.items())]

    risk_counts = Counter(str(row.risk_level or "UNKNOWN") for row in transactions)
    risk_distribution = [{"label": label, "count": count} for label, count in risk_counts.most_common()]
    hour_counts = Counter(row.occurred_at.hour for row in fraud_transactions)
    fraud_by_hour = [{"label": f"{hour:02d}", "hour": hour, "count": hour_counts[hour]} for hour in sorted(hour_counts)]

    fraud_by_category = _grouped(fraud_transactions, lambda row: row.merchant_category or (row.merchant.category if row.merchant else None))
    fraud_by_device = _grouped(fraud_transactions, lambda row: row.device.fingerprint if row.device else (str(row.device_id) if row.device_id else (row.metadata_json or {}).get("device_fingerprint")))
    fraud_by_location = _grouped(fraud_transactions, lambda row: row.location)

    bins = [(0, 100), (100, 500), (500, 1000), (1000, 5000), (5000, 10000), (10000, 50000), (50000, None)]
    amount_distribution = []
    for lower, upper in bins:
        selected = [row for row in transactions if float(row.amount) >= lower and (upper is None or float(row.amount) < upper)]
        amount_distribution.append({"label": f">={lower}" if upper is None else f"{lower}-{upper}", "count": len(selected), "fraud_transactions": sum(_fraud(row) for row in selected)})

    actual_fraud = len(fraud_transactions)
    detected_fraud = sum(_detected(row) for row in fraud_transactions)
    false_positives = sum(not _fraud(row) and _detected(row) for row in transactions)
    detected_total = sum(_detected(row) for row in transactions)
    detection_performance = {
        "fraud_transactions": actual_fraud,
        "detected_fraud_transactions": detected_fraud,
        "missed_fraud_transactions": actual_fraud - detected_fraud,
        "false_positive_transactions": false_positives,
        "precision": round(detected_fraud / detected_total * 100, 2) if detected_total else None,
        "recall": round(detected_fraud / actual_fraud * 100, 2) if actual_fraud else None,
        "reviewed_or_blocked": detected_total,
    }

    feedback_query = select(InvestigationFeedback).join(InvestigationCase, InvestigationCase.id == InvestigationFeedback.case_id).order_by(InvestigationFeedback.created_at.asc())
    if canonical_role(getattr(user, "role", "")) != "ADMIN":
        feedback_query = feedback_query.where(InvestigationCase.alert.has(user_id=user.id))
    feedback = list(db.scalars(feedback_query).all())
    feedback_by_day: defaultdict[str, dict[str, int]] = defaultdict(lambda: {"false_positives": 0, "reviewed": 0})
    for row in feedback:
        key = row.created_at.date().isoformat()
        feedback_by_day[key]["reviewed"] += 1
        feedback_by_day[key]["false_positives"] += row.label == "FALSE_POSITIVE"
    false_positive_trend = [{"label": key, **value} for key, value in sorted(feedback_by_day.items())]

    fraud_amount = sum(float(row.amount) for row in fraud_transactions)
    prevented = sum(float(row.amount) for row in fraud_transactions if row.decision == "BLOCK")
    financial_exposure = {"fraud_amount": fraud_amount, "prevented_amount": prevented, "unprevented_amount": fraud_amount - prevented, "total_transaction_amount": sum(float(row.amount) for row in transactions)}

    attack_groups: defaultdict[str, list[Transaction]] = defaultdict(list)
    for row in transactions:
        if row.fraud_scenario:
            attack_groups[row.fraud_scenario].append(row)
    attack_simulation_performance = [{"label": name, "transactions": len(rows), "fraud_transactions": sum(_fraud(row) for row in rows), "detected_transactions": sum(_detected(row) for row in rows), "detection_rate": round(sum(_detected(row) for row in rows) / len(rows) * 100, 2) if rows else 0.0} for name, rows in sorted(attack_groups.items())]

    clusters: list[dict[str, object]] = []
    try:
        result = NetworkIntelligence(db, user_id=None if canonical_role(getattr(user, "role", "")) == "ADMIN" else user.id).suspicious_clusters()
        clusters = [{"cluster_id": cluster.cluster_id, "node_count": len(cluster.nodes), "transaction_count": cluster.transaction_count, "suspicious_transaction_count": cluster.suspicious_transaction_count, "network_score": cluster.network_score, "explanation": cluster.explanation} for cluster in result.clusters]
    except ValueError:
        clusters = []

    return AnalyticsOverview(
        fraud_trend=fraud_trend,
        risk_distribution=risk_distribution,
        fraud_by_hour=fraud_by_hour,
        fraud_by_merchant_category=fraud_by_category,
        fraud_by_device=fraud_by_device,
        fraud_by_location=fraud_by_location,
        amount_distribution=amount_distribution,
        detection_performance=detection_performance,
        false_positive_trend=false_positive_trend,
        financial_exposure=financial_exposure,
        attack_simulation_performance=attack_simulation_performance,
        network_risk_clusters=clusters,
    )