"""Dynamic Database-backed Dashboard Analytics.

All metrics are computed strictly from database tables (Transaction, FraudAlert,
Merchant, Device). No hardcoded numbers.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Device, FraudAlert, Merchant, Transaction, User
from app.schemas.transactions import DashboardStatistics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/statistics", response_model=DashboardStatistics)
def statistics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DashboardStatistics:
    # Role-based scoping: Admins view system-wide operations; standard users view their account
    is_admin = getattr(user, "role", "user") == "admin"
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
    )
