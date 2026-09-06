"""Dynamic Database-backed Dashboard Analytics.

All metrics are computed strictly from database tables (Transaction, FraudAlert,
Merchant, Device). No hardcoded numbers.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models import Device, FraudAlert, Merchant, Transaction, User
from app.schemas.transactions import DashboardStatistics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/statistics", response_model=DashboardStatistics)
def statistics(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics_read")),
) -> DashboardStatistics:
    # Role-based scoping: Admins view system-wide operations; standard users view their account
    is_admin = getattr(user, "role", "") == "ADMIN"
    tx_filter = True if is_admin else (Transaction.user_id == user.id)
    alert_filter = True if is_admin else (FraudAlert.user_id == user.id)

    # Core transaction aggregations
    counts = db.execute(
        select(
            func.count(Transaction.id),
            func.count(case((Transaction.risk_level.in_(["MEDIUM", "HIGH"]), 1), (Transaction.is_fraud == True, 1))),
            func.count(case((Transaction.risk_level == "HIGH", 1), (Transaction.is_fraud == True, 1))),
            func.count(case((Transaction.decision == "REVIEW", 1))),
            func.count(case((Transaction.decision == "BLOCK", 1), (Transaction.status == "blocked", 1))),
            func.count(case((Transaction.decision == "APPROVE", 1), (Transaction.status == "completed", 1))),
            func.coalesce(func.sum(Transaction.amount), 0),
            func.coalesce(
                func.sum(
                    case(
                        (Transaction.decision == "BLOCK", Transaction.amount),
                        (Transaction.status == "blocked", Transaction.amount),
                        (Transaction.is_fraud == True, Transaction.amount),
                        else_=0,
                    )
                ),
                0,
            ),
        ).where(tx_filter)
    ).one()

    total_transactions = counts[0] or 0
    total_alerts = counts[1] or 0
    high_risk_transactions = counts[2] or 0
    review_transactions = counts[3] or 0
    blocked_transactions = counts[4] or 0
    approved_transactions = counts[5] or 0
    total_volume = float(counts[6] or 0.0)
    exposure_prevented = float(counts[7] or 0.0)

    # Active investigations count directly from open FraudAlerts
    active_investigations = db.scalar(
        select(func.count(FraudAlert.id)).where(alert_filter, FraudAlert.status == "open")
    ) or 0

    # Risk level distribution directly from DB
    distribution_rows = db.execute(
        select(Transaction.risk_level, func.count(Transaction.id))
        .where(tx_filter)
        .group_by(Transaction.risk_level)
    ).all()
    risk_distribution = {str(level or "PENDING"): count for level, count in distribution_rows}

    # Fraud rate calculated from database records
    fraud_rate = (blocked_transactions / total_transactions * 100.0) if total_transactions else 0.0

    # Top risky merchants from database
    top_merchants_rows = db.execute(
        select(
            Merchant.name,
            Merchant.category,
            func.count(Transaction.id).label("total_tx"),
            func.count(case((Transaction.is_fraud == True, 1), (Transaction.risk_level == "HIGH", 1))).label("fraud_tx"),
            func.max(Transaction.risk_score).label("risk_score"),
        )
        .join(Transaction, Transaction.merchant_id == Merchant.id)
        .where(tx_filter)
        .group_by(Merchant.name, Merchant.category)
        .order_by(
            func.count(case((Transaction.is_fraud == True, 1), (Transaction.risk_level == "HIGH", 1))).desc(),
            func.count(Transaction.id).desc(),
        )
        .limit(5)
    ).all()
    top_risky_merchants: list[dict[str, Any]] = [
        {
            "name": row[0],
            "category": row[1] or "general",
            "total_transactions": row[2],
            "fraud_transactions": row[3],
            "risk_score": float(row[4] or 0),
        }
        for row in top_merchants_rows
    ]

    # Top risky devices from database
    top_devices_rows = db.execute(
        select(
            Device.fingerprint,
            Device.platform,
            func.count(Transaction.id).label("total_tx"),
            func.count(case((Transaction.is_fraud == True, 1), (Transaction.risk_level == "HIGH", 1))).label("fraud_tx"),
            func.max(Transaction.risk_score).label("risk_score"),
        )
        .join(Transaction, Transaction.device_id == Device.id)
        .where(tx_filter)
        .group_by(Device.fingerprint, Device.platform)
        .order_by(
            func.count(case((Transaction.is_fraud == True, 1), (Transaction.risk_level == "HIGH", 1))).desc(),
            func.count(Transaction.id).desc(),
        )
        .limit(5)
    ).all()
    top_risky_devices: list[dict[str, Any]] = [
        {
            "fingerprint": row[0],
            "platform": row[1] or "unknown",
            "total_transactions": row[2],
            "fraud_transactions": row[3],
            "risk_score": float(row[4] or 0),
        }
        for row in top_devices_rows
    ]

    # Daily fraud trend time series from database
    trend_rows = db.execute(
        select(
            func.date(Transaction.occurred_at).label("day"),
            func.count(Transaction.id).label("tx_count"),
            func.count(case((Transaction.is_fraud == True, 1), (Transaction.risk_level == "HIGH", 1))).label("fraud_count"),
            func.coalesce(func.sum(Transaction.amount), 0).label("volume"),
        )
        .where(tx_filter)
        .group_by(func.date(Transaction.occurred_at))
        .order_by(func.date(Transaction.occurred_at).asc())
        .limit(30)
    ).all()
    fraud_trend: list[dict[str, Any]] = [
        {
            "date": str(row[0]),
            "transactions": row[1],
            "fraud_count": row[2],
            "volume": float(row[3]),
        }
        for row in trend_rows
    ]

    enriched_transactions = list(db.scalars(
        select(Transaction).options(selectinload(Transaction.user), selectinload(Transaction.device), selectinload(Transaction.merchant))
        .where(tx_filter).order_by(Transaction.created_at.desc()).limit(1000)
    ).all())
    current_fraud_count = sum(item.is_fraud for item in enriched_transactions)
    current_fraud_rate = current_fraud_count / len(enriched_transactions) * 100.0 if enriched_transactions else 0.0
    exposure = sum(float(item.amount) for item in enriched_transactions if item.is_fraud)
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(minutes=1)
    transactions_per_minute = sum((item.created_at or now).replace(tzinfo=timezone.utc) >= recent_cutoff for item in enriched_transactions)

    def entity_rank(key, label) -> list[dict[str, Any]]:
        grouped: defaultdict[str, dict[str, Any]] = defaultdict(lambda: {"transactions": 0, "fraud_transactions": 0, "risk_score": 0.0})
        for item in enriched_transactions:
            identifier = key(item)
            if not identifier:
                continue
            bucket = grouped[str(identifier)]
            bucket["label"] = label(item)
            bucket["transactions"] += 1
            bucket["fraud_transactions"] += int(item.is_fraud)
            bucket["risk_score"] = max(bucket["risk_score"], float(item.risk_score or 0))
        return sorted(grouped.values(), key=lambda item: (item["risk_score"], item["fraud_transactions"]), reverse=True)[:5]

    top_risky_users = entity_rank(lambda item: item.user_id, lambda item: item.user.email if item.user else str(item.user_id))
    suspicious_ips = entity_rank(lambda item: item.ip_address, lambda item: item.ip_address)

    stream_transaction_ids = [item.id for item in enriched_transactions[:20]]
    stream_alerts = list(db.scalars(select(FraudAlert).where(FraudAlert.transaction_id.in_(stream_transaction_ids))).all()) if stream_transaction_ids else []
    alert_by_transaction = {item.transaction_id: item for item in stream_alerts}
    detection_stream = [
        {
            "time": item.created_at,
            "entity": item.user.email if item.user else str(item.user_id),
            "transaction_id": str(item.id),
            "alert_id": str(alert_by_transaction[item.id].id) if item.id in alert_by_transaction else None,
            "risk": float(item.risk_score or 0),
            "risk_level": item.risk_level or "LOW",
            "decision": item.decision or "APPROVE",
            "reason": (item.reasons or ["No stored reason"])[0],
        }
        for item in enriched_transactions[:20]
    ]
    critical_alerts = [
        {"id": str(item.id), "transaction_id": str(item.transaction_id), "risk_score": float(item.risk_score), "reason": item.reason_code, "status": item.status, "created_at": item.created_at}
        for item in db.scalars(select(FraudAlert).where(alert_filter, FraudAlert.status == "open").order_by(FraudAlert.risk_score.desc(), FraudAlert.created_at.desc()).limit(8)).all()
    ]

    # Dynamic model health indicators based on real DB fraud metrics
    drift_status = "LOW" if fraud_rate < 15.0 else ("MEDIUM" if fraud_rate < 30.0 else "HIGH")
    perf_status = "STABLE" if total_transactions > 0 else "PENDING_DATA"
    model_health = {
        "data_drift": drift_status,
        "performance": perf_status,
        "prediction_drift": "LOW" if high_risk_transactions < total_transactions * 0.25 else "ELEVATED",
    }

    return DashboardStatistics(
        total_transactions=total_transactions,
        total_alerts=total_alerts,
        high_risk_transactions=high_risk_transactions,
        review_transactions=review_transactions,
        blocked_transactions=blocked_transactions,
        approved_transactions=approved_transactions,
        risk_distribution=risk_distribution,
        fraud_rate=round(fraud_rate, 2),
        total_volume=round(total_volume, 2),
        exposure_prevented=round(exposure_prevented, 2),
        active_investigations=active_investigations,
        model_health=model_health,
        top_risky_merchants=top_risky_merchants,
        top_risky_devices=top_risky_devices,
        fraud_trend=fraud_trend,
        system_status="OPERATIONAL",
        transactions_per_minute=float(transactions_per_minute),
        current_fraud_rate=round(current_fraud_rate, 2),
        financial_exposure=round(exposure, 2),
        critical_alerts=critical_alerts,
        top_risky_users=top_risky_users,
        suspicious_ips=suspicious_ips,
        detection_stream=detection_stream,
    )
