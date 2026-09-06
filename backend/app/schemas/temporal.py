from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WindowMetrics(BaseModel):
    window_name: str  # "30s", "5m", "30m", "24h"
    window_seconds: int
    transaction_count: int
    total_amount: float
    unique_merchants: int
    unique_devices: int
    unique_locations: int
    failed_attempts: int
    repeated_amounts_count: int
    rapid_intervals_count: int  # intervals < 15 seconds
    min_interval_seconds: float | None
    avg_interval_seconds: float | None


class RollingWindowFeatures(BaseModel):
    window_30s: WindowMetrics
    window_5m: WindowMetrics
    window_30m: WindowMetrics
    window_24h: WindowMetrics


class TemporalSequenceEvent(BaseModel):
    transaction_id: UUID
    timestamp: datetime
    time_since_previous_seconds: float | None
    time_since_previous_formatted: str
    amount: float
    currency: str
    location: str | None
    device: str | None
    ip_address: str | None
    merchant: str | None
    merchant_category: str | None
    status: str
    is_fraud: bool
    risk_signals: list[str] = Field(default_factory=list)


class SuspiciousSequence(BaseModel):
    sequence_id: str
    user_id: UUID
    user_email: str | None = None
    pattern_type: str  # "TRANSACTION_BURST", "RAPID_REPEATED_PAYMENTS", "CARD_TESTING", "SPENDING_ACCELERATION", "MULTIPLE_MERCHANTS_RAPID"
    pattern_title: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    risk_score: float  # 0.0 to 100.0
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    duration_formatted: str
    transaction_count: int
    total_amount: float
    events: list[TemporalSequenceEvent]
    rolling_features_at_peak: RollingWindowFeatures | None = None
    explanation: str
    historical_baseline_comparison: dict[str, Any] = Field(default_factory=dict)


class UserTemporalAnalysisResponse(BaseModel):
    user_id: UUID
    user_email: str
    analyzed_at: datetime
    total_transactions_analyzed: int
    current_rolling_windows: RollingWindowFeatures
    detected_sequences: list[SuspiciousSequence]
    full_event_timeline: list[TemporalSequenceEvent]
    summary: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class SequenceListResponse(BaseModel):
    items: list[SuspiciousSequence]
    total: int
    patterns_summary: dict[str, int]


class TransactionTemporalContextResponse(BaseModel):
    transaction_id: UUID
    occurred_at: datetime
    rolling_windows: RollingWindowFeatures
    preceding_events: list[TemporalSequenceEvent]
    succeeding_events: list[TemporalSequenceEvent]
    triggered_patterns: list[str]
    time_since_previous_seconds: float | None
    time_since_previous_formatted: str
