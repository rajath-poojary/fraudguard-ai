from typing import Any

from pydantic import BaseModel, Field


class SignalFeedbackMetric(BaseModel):
    signal: str
    false_positive_count: int
    reviewed_count: int
    false_positive_rate: float


class FeedbackEvaluationRecord(BaseModel):
    case_id: str
    transaction_id: str
    label: str
    fraud_probability: float | None = None
    risk_score: float | None = None
    reason_codes: list[str] = Field(default_factory=list)
    created_at: str


class FeedbackAnalyticsResponse(BaseModel):
    false_positive_count: int
    false_positive_rate: float
    fraud_confirmation_count: int
    fraud_confirmation_rate: float
    uncertain_count: int
    reviewed_count: int
    review_rate: float
    signal_metrics: list[SignalFeedbackMetric]
    evaluation_records: list[FeedbackEvaluationRecord]
    retraining_triggered: bool = False
    evaluation_note: str = "Feedback is stored for evaluation; production retraining is never triggered automatically."