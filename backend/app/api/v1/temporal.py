"""Temporal Fraud Detection API Endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.entities import User
from app.schemas.temporal import (
    SequenceListResponse,
    SuspiciousSequence,
    TransactionTemporalContextResponse,
    UserTemporalAnalysisResponse,
)
from app.services.temporal_engine import TemporalEngine

router = APIRouter(prefix="/temporal", tags=["temporal-fraud-detection"])


@router.get(
    "/sequences",
    response_model=SequenceListResponse,
    summary="List suspicious transaction sequences across accounts",
)
def list_suspicious_sequences(
    pattern: str | None = Query(
        default=None,
        description="Filter by pattern: TRANSACTION_BURST, RAPID_REPEATED_PAYMENTS, CARD_TESTING, SPENDING_ACCELERATION, MULTIPLE_MERCHANTS_RAPID",
    ),
    severity: str | None = Query(
        default=None,
        description="Filter by severity: LOW, MEDIUM, HIGH, CRITICAL",
    ),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SequenceListResponse:
    """Retrieve detected suspicious temporal sequences with multi-window evidence."""
    engine = TemporalEngine(db=db)
    is_admin = getattr(current_user, "role", "user") == "admin"

    if is_admin:
        sequences = engine.scan_system_suspicious_sequences(
            pattern_type=pattern,
            severity=severity,
            limit=limit,
        )
    else:
        # Standard user: only their sequences
        try:
            analysis = engine.analyze_user_sequences(current_user.id)
            sequences = analysis.detected_sequences
            if pattern:
                sequences = [s for s in sequences if s.pattern_type == pattern]
            if severity:
                sequences = [s for s in sequences if s.severity == severity]
        except Exception:
            sequences = []

    # Patterns count summary
    patterns_summary = {
        "TRANSACTION_BURST": sum(1 for s in sequences if s.pattern_type == "TRANSACTION_BURST"),
        "RAPID_REPEATED_PAYMENTS": sum(1 for s in sequences if s.pattern_type == "RAPID_REPEATED_PAYMENTS"),
        "CARD_TESTING": sum(1 for s in sequences if s.pattern_type == "CARD_TESTING"),
        "SPENDING_ACCELERATION": sum(1 for s in sequences if s.pattern_type == "SPENDING_ACCELERATION"),
        "MULTIPLE_MERCHANTS_RAPID": sum(1 for s in sequences if s.pattern_type == "MULTIPLE_MERCHANTS_RAPID"),
    }

    return SequenceListResponse(
        items=sequences,
        total=len(sequences),
        patterns_summary=patterns_summary,
    )


@router.get(
    "/users/{user_id}/analysis",
    response_model=UserTemporalAnalysisResponse,
    summary="Analyze rolling temporal windows and sequences for a user",
)
def get_user_temporal_analysis(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserTemporalAnalysisResponse:
    """Analyze transaction stream, rolling windows (30s, 5m, 30m, 24h), and delta-t timeline."""
    is_admin = getattr(current_user, "role", "user") == "admin"
    if not is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You can only inspect your own temporal sequences.",
        )

    engine = TemporalEngine(db=db)
    try:
        return engine.analyze_user_sequences(user_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@router.get(
    "/transactions/{transaction_id}/context",
    response_model=TransactionTemporalContextResponse,
    summary="Fetch rolling window and sequential context around a transaction",
)
def get_transaction_temporal_context(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransactionTemporalContextResponse:
    """Fetch preceding & succeeding events, delta-t interval, and rolling windows for a transaction."""
    engine = TemporalEngine(db=db)
    try:
        return engine.get_transaction_temporal_context(transaction_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
