from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Transaction, User
from app.schemas.transactions import DashboardStatistics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/statistics", response_model=DashboardStatistics)
def statistics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DashboardStatistics:
    counts = db.execute(
        select(
            func.count(Transaction.id),
            func.count(case((Transaction.risk_level.in_(["MEDIUM", "HIGH"]), 1))),
            func.count(case((Transaction.risk_level == "HIGH", 1))),
            func.count(case((Transaction.decision == "REVIEW", 1))),
            func.count(case((Transaction.decision == "BLOCK", 1))),
            func.count(case((Transaction.decision == "APPROVE", 1))),
        ).where(Transaction.user_id == user.id)
    ).one()
    return DashboardStatistics(
        total_transactions=counts[0],
        total_alerts=counts[1],
        high_risk_transactions=counts[2],
        review_transactions=counts[3],
        blocked_transactions=counts[4],
        approved_transactions=counts[5],
    )
