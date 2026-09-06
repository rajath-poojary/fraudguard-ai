from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DistributionBucket(BaseModel):
    key: str
    count: int
    percentage: float


class HourlyActivity(BaseModel):
    hour: int
    count: int
    percentage: float


class DayOfWeekActivity(BaseModel):
    day: int  # 0 = Monday, 6 = Sunday
    day_name: str
    count: int
    percentage: float


class BehavioralBaseline(BaseModel):
    user_id: UUID
    calculated_at: datetime
    baseline_window_days: int
    historical_transaction_count: int
    has_sufficient_history: bool
    average_transaction_amount: float
    median_transaction_amount: float
    standard_deviation: float
    min_transaction_amount: float
    max_transaction_amount: float
    typical_amount_range: list[float]  # [lower_bound, upper_bound]
    average_daily_frequency: float
    burstiness_baseline: float
    failed_transaction_count: int
    historical_fraud_association: int
    hourly_distribution: list[HourlyActivity]
    day_of_week_distribution: list[DayOfWeekActivity]
    frequent_locations: list[DistributionBucket]
    frequent_merchant_categories: list[DistributionBucket]
    known_devices: list[str]
    known_ip_addresses: list[str]


class CurrentActivity(BaseModel):
    transaction_id: UUID | None
    occurred_at: datetime
    amount: float
    currency: str
    merchant_category: str | None
    location: str | None
    device_id: UUID | None
    device_fingerprint: str | None
    ip_address: str | None
    payment_method: str | None
    status: str
    recent_transaction_count_30d: int
    recent_transaction_count_24h: int
    recent_burstiness: float


class DeviationMetric(BaseModel):
    name: str
    label: str
    value: float
    score: float  # Normalized 0.0 to 1.0
    level: str  # "normal", "moderate", "high", "extreme", "insufficient_history"
    explanation: str


class DeviationAnalysis(BaseModel):
    amount_deviation: DeviationMetric
    transaction_frequency_deviation: DeviationMetric
    time_of_day_deviation: DeviationMetric
    day_of_week_deviation: DeviationMetric
    location_deviation: DeviationMetric
    merchant_category_deviation: DeviationMetric
    device_novelty: DeviationMetric
    ip_novelty: DeviationMetric
    transaction_burstiness: DeviationMetric
    composite_deviation_score: float  # 0.0 to 1.0
    overall_risk_level: str  # "LOW", "MEDIUM", "HIGH"


class RiskIndicator(BaseModel):
    code: str
    title: str
    severity: str  # "info", "low", "medium", "high"
    description: str


class TimelinePoint(BaseModel):
    timestamp: datetime
    transaction_id: UUID
    amount: float
    location: str | None
    merchant_category: str | None
    deviation_score: float
    is_fraud: bool
    status: str


class UserBehaviorProfileResponse(BaseModel):
    user_id: UUID
    user_email: str
    user_display_name: str | None
    account_age_days: int | None
    behavioral_baseline: BehavioralBaseline
    current_activity: CurrentActivity | None
    current_deviation: DeviationAnalysis | None
    risk_indicators: list[RiskIndicator]
    recent_activity: list[CurrentActivity]
    behavior_timeline: list[TimelinePoint]

    model_config = ConfigDict(from_attributes=True)


class UserProfileSummary(BaseModel):
    user_id: UUID
    email: str
    display_name: str | None
    transaction_count: int
    last_active: datetime | None
    composite_deviation_score: float
    overall_risk_level: str
    top_risk_indicator: str | None
