"""Behavioral Intelligence API Endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.entities import User
from app.schemas.behavior import (
    UserBehaviorProfileResponse,
    UserProfileSummary,
)
from app.services.behavior_engine import BehaviorEngine

router = APIRouter(tags=["behavioral-intelligence"])


@router.get(
    "/users/{user_id}/behavior-profile",
    response_model=UserBehaviorProfileResponse,
    summary="Get user behavioral profile and baseline analysis",
)
def get_user_behavior_profile(
    user_id: UUID,
    current_transaction_id: UUID | None = Query(
        default=None,
        description="Optional transaction ID to evaluate as current activity against historical baseline",
    ),
    window_days: int = Query(
        default=90,
        ge=7,
        le=365,
        description="Rolling baseline window length in days",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserBehaviorProfileResponse:
    """Calculate historical behavioral baseline and multi-dimensional deviations.

    Access Control:
    - Admins can query any user's profile.
    - Regular users can only query their own behavioral profile.

    Guarantee:
    - The current transaction is strictly excluded from historical baseline calculations.
    """
    # Authorization check
    is_admin = getattr(current_user, "role", "user") == "admin"
    if not is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You may only view your own behavioral intelligence profile.",
        )

    engine = BehaviorEngine(db=db, baseline_window_days=window_days)
    try:
        return engine.get_user_behavior_profile(
            user_id=user_id,
            current_transaction_id=current_transaction_id,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


@router.get(
    "/behavioral/profiles",
    response_model=dict[str, Any],
    summary="List behavioral profile summaries for accounts",
)
def list_behavioral_profiles(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """List summary behavioral profiles across accounts for operator selection."""
    engine = BehaviorEngine(db=db)
    is_admin = getattr(current_user, "role", "user") == "admin"

    if is_admin:
        summaries = engine.list_user_summaries(limit=limit)
    else:
        # Standard user only sees their own summary
        try:
            profile = engine.get_user_behavior_profile(current_user.id)
            score = (
                profile.current_deviation.composite_deviation_score
                if profile.current_deviation
                else 0.0
            )
            level = (
                profile.current_deviation.overall_risk_level
                if profile.current_deviation
                else "LOW"
            )
            top_indicator = (
                profile.risk_indicators[0].title
                if profile.risk_indicators
                else "Normal behavior"
            )
            summaries = [
                UserProfileSummary(
                    user_id=current_user.id,
                    email=current_user.email,
                    display_name=current_user.display_name,
                    transaction_count=profile.behavioral_baseline.historical_transaction_count
                    + (1 if profile.current_activity else 0),
                    last_active=(
                        profile.current_activity.occurred_at
                        if profile.current_activity
                        else None
                    ),
                    composite_deviation_score=score,
                    overall_risk_level=level,
                    top_risk_indicator=top_indicator,
                )
            ]
        except Exception:
            summaries = []

    return {
        "items": [s.model_dump() for s in summaries],
        "total": len(summaries),
    }
