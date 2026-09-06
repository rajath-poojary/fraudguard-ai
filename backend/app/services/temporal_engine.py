"""Temporal Fraud Detection Engine.

Analyzes transaction sequences across multiple rolling time windows (30s, 5m, 30m, 24h)
and detects complex temporal attack patterns:
- Transaction bursts
- Rapid repeated payments
- Card testing sequences
- Sudden spending acceleration
- Multiple merchants in short time spans

Integrates historical behavioral baselines to ensure non-static, adaptive detection.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Sequence
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Transaction, User
from app.schemas.temporal import (
    RollingWindowFeatures,
    SuspiciousSequence,
    TemporalSequenceEvent,
    TransactionTemporalContextResponse,
    UserTemporalAnalysisResponse,
    WindowMetrics,
)
from app.services.behavior_engine import BehaviorEngine


def _ensure_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_duration(seconds: float) -> str:
    """Format duration in seconds into human-readable string."""
    if seconds < 0:
        return "0s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    rem_sec = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {rem_sec}s"
    hours = int(minutes // 60)
    rem_min = int(minutes % 60)
    return f"{hours}h {rem_min}m"


class TemporalEngine:
    """Engine for multi-resolution rolling window sequence analysis and pattern detection."""

    def __init__(self, db: Session):
        self.db = db
        self.behavior_engine = BehaviorEngine(db=db)

    def compute_rolling_windows(
        self,
        transactions: Sequence[Transaction],
        reference_time: datetime,
    ) -> RollingWindowFeatures:
        """Calculate rolling window metrics across 30s, 5m, 30m, and 24h leading up to reference_time."""
        ref_utc = _ensure_utc(reference_time)
        # Transactions strictly up to reference_time
        sorted_txs = sorted(
            [t for t in transactions if _ensure_utc(t.occurred_at) <= ref_utc],
            key=lambda t: _ensure_utc(t.occurred_at),
        )

        w30s = self._compute_single_window("30s", 30, sorted_txs, ref_utc)
        w5m = self._compute_single_window("5m", 300, sorted_txs, ref_utc)
        w30m = self._compute_single_window("30m", 1800, sorted_txs, ref_utc)
        w24h = self._compute_single_window("24h", 86400, sorted_txs, ref_utc)

        return RollingWindowFeatures(
            window_30s=w30s,
            window_5m=w5m,
            window_30m=w30m,
            window_24h=w24h,
        )

    def _compute_single_window(
        self,
        window_name: str,
        window_seconds: int,
        sorted_txs: list[Transaction],
        ref_utc: datetime,
    ) -> WindowMetrics:
        """Compute metrics for a specific window duration."""
        cutoff = ref_utc - timedelta(seconds=window_seconds)
        window_txs = [t for t in sorted_txs if _ensure_utc(t.occurred_at) >= cutoff]

        count = len(window_txs)
        total_amt = round(sum(float(t.amount) for t in window_txs), 2)

        # Unique counts
        merchants = {str(t.merchant_id) if t.merchant_id else t.merchant_category for t in window_txs if t.merchant_id or t.merchant_category}
        devices = {
            str(t.device_id) if t.device_id else (t.metadata_json or {}).get("device_fingerprint")
            for t in window_txs
            if t.device_id or (t.metadata_json and (t.metadata_json or {}).get("device_fingerprint"))
        }
        devices.discard(None)
        locations = {t.location for t in window_txs if t.location}

        # Failed attempts
        failed_count = sum(
            1 for t in window_txs
            if (t.status or "").lower() in ("failed", "blocked", "declined", "rejected", "error")
        )

        # Repeated amounts
        amounts = [round(float(t.amount), 2) for t in window_txs]
        amt_counts = Counter(amounts)
        repeated_amt_count = sum(c for amt, c in amt_counts.items() if c > 1)

        # Inter-arrival intervals in window
        intervals: list[float] = []
        rapid_intervals_count = 0
        for i in range(1, len(window_txs)):
            dt = (_ensure_utc(window_txs[i].occurred_at) - _ensure_utc(window_txs[i - 1].occurred_at)).total_seconds()
            intervals.append(dt)
            if dt <= 15.0:
                rapid_intervals_count += 1

        min_interval = round(min(intervals), 2) if intervals else None
        avg_interval = round(sum(intervals) / len(intervals), 2) if intervals else None

        return WindowMetrics(
            window_name=window_name,
            window_seconds=window_seconds,
            transaction_count=count,
            total_amount=total_amt,
            unique_merchants=len(merchants),
            unique_devices=len(devices),
            unique_locations=len(locations),
            failed_attempts=failed_count,
            repeated_amounts_count=repeated_amt_count,
            rapid_intervals_count=rapid_intervals_count,
            min_interval_seconds=min_interval,
            avg_interval_seconds=avg_interval,
        )

    def analyze_user_sequences(self, user_id: UUID) -> UserTemporalAnalysisResponse:
        """Run temporal sequence analysis on a user's chronological transaction stream."""
        user = self.db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise ValueError(f"User {user_id} not found")

        txs = list(
            self.db.scalars(
                select(Transaction)
                .where(Transaction.user_id == user_id)
                .order_by(Transaction.occurred_at.asc())
            ).all()
        )

        latest_time = _ensure_utc(txs[-1].occurred_at) if txs else _ensure_utc(datetime.now(timezone.utc))
        current_windows = self.compute_rolling_windows(txs, latest_time)

        # Build baseline for dynamic comparison
        baseline = None
        try:
            profile = self.behavior_engine.get_user_behavior_profile(user_id)
            baseline = profile.behavioral_baseline
        except Exception:
            pass

        # Build full sequence events with delta-t
        events: list[TemporalSequenceEvent] = []
        for i, tx in enumerate(txs):
            prev_tx = txs[i - 1] if i > 0 else None
            dt = (
                (_ensure_utc(tx.occurred_at) - _ensure_utc(prev_tx.occurred_at)).total_seconds()
                if prev_tx
                else None
            )
            dt_fmt = _format_duration(dt) if dt is not None else "Initial Event"

            dev_fp = None
            if tx.metadata_json and isinstance(tx.metadata_json, dict):
                dev_fp = tx.metadata_json.get("device_fingerprint")

            events.append(
                TemporalSequenceEvent(
                    transaction_id=tx.id,
                    timestamp=tx.occurred_at,
                    time_since_previous_seconds=round(dt, 2) if dt is not None else None,
                    time_since_previous_formatted=dt_fmt,
                    amount=float(tx.amount),
                    currency=tx.currency,
                    location=tx.location,
                    device=dev_fp or (str(tx.device_id) if tx.device_id else None),
                    ip_address=tx.ip_address,
                    merchant=tx.metadata_json.get("merchant") if tx.metadata_json else None,
                    merchant_category=tx.merchant_category,
                    status=tx.status,
                    is_fraud=tx.is_fraud,
                    risk_signals=[],
                )
            )

        # Detect temporal patterns across sliding clusters
        detected_sequences = self._detect_patterns_in_stream(user, txs, events, baseline)

        summary = {
            "total_transactions": len(txs),
            "suspicious_sequences_detected": len(detected_sequences),
            "critical_sequences": sum(1 for s in detected_sequences if s.severity == "CRITICAL"),
            "high_sequences": sum(1 for s in detected_sequences if s.severity == "HIGH"),
            "burst_count": sum(1 for s in detected_sequences if s.pattern_type == "TRANSACTION_BURST"),
            "card_testing_count": sum(1 for s in detected_sequences if s.pattern_type == "CARD_TESTING"),
            "repeated_payment_count": sum(1 for s in detected_sequences if s.pattern_type == "RAPID_REPEATED_PAYMENTS"),
            "spending_acceleration_count": sum(1 for s in detected_sequences if s.pattern_type == "SPENDING_ACCELERATION"),
            "merchant_hopping_count": sum(1 for s in detected_sequences if s.pattern_type == "MULTIPLE_MERCHANTS_RAPID"),
        }

        return UserTemporalAnalysisResponse(
            user_id=user.id,
            user_email=user.email,
            analyzed_at=latest_time,
            total_transactions_analyzed=len(txs),
            current_rolling_windows=current_windows,
            detected_sequences=detected_sequences,
            full_event_timeline=events,
            summary=summary,
        )

    def _detect_patterns_in_stream(
        self,
        user: User,
        txs: list[Transaction],
        events: list[TemporalSequenceEvent],
        baseline: Any | None,
    ) -> list[SuspiciousSequence]:
        """Scan transaction event stream for multi-event temporal patterns."""
        if len(txs) < 2:
            return []

        detected: list[SuspiciousSequence] = []
        tx_count = len(txs)

        # Baseline parameters for dynamic comparison (non-static)
        baseline_avg_amt = baseline.average_transaction_amount if baseline and baseline.has_sufficient_history else 50.0
        baseline_daily_freq = baseline.average_daily_frequency if baseline and baseline.has_sufficient_history else 2.0
        baseline_min_amt = baseline.min_transaction_amount if baseline and baseline.has_sufficient_history else 10.0

        # Map transaction ID to event
        event_map = {e.transaction_id: e for e in events}

        # 1. Slide a window over transactions to find clusters
        i = 0
        while i < tx_count:
            start_tx = txs[i]
            start_time = _ensure_utc(start_tx.occurred_at)

            # Look ahead up to 30 minutes
            j = i
            window_txs: list[Transaction] = []
            while j < tx_count:
                t_j = txs[j]
                dt = (_ensure_utc(t_j.occurred_at) - start_time).total_seconds()
                if dt <= 1800:  # 30-minute episode window
                    window_txs.append(t_j)
                    j += 1
                else:
                    break

            if len(window_txs) >= 2:
                # Check for patterns within this candidate episode
                episode_seqs = self._evaluate_episode_patterns(
                    user=user,
                    episode_txs=window_txs,
                    event_map=event_map,
                    baseline_avg_amt=baseline_avg_amt,
                    baseline_daily_freq=baseline_daily_freq,
                    baseline_min_amt=baseline_min_amt,
                )
                detected.extend(episode_seqs)

            # Advance by step
            i += max(1, len(window_txs) // 2)

        # Deduplicate detected sequences by start & pattern_type
        unique_seqs: list[SuspiciousSequence] = []
        seen_keys = set()
        for seq in detected:
            key = (seq.pattern_type, seq.start_time.isoformat(), seq.transaction_count)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_seqs.append(seq)

        # Sort by severity and timestamp
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        unique_seqs.sort(key=lambda s: (severity_order.get(s.severity, 4), s.start_time), reverse=False)

        return unique_seqs

    def _evaluate_episode_patterns(
        self,
        user: User,
        episode_txs: list[Transaction],
        event_map: dict[UUID, TemporalSequenceEvent],
        baseline_avg_amt: float,
        baseline_daily_freq: float,
        baseline_min_amt: float,
    ) -> list[SuspiciousSequence]:
        """Test an episode for all 5 specific temporal fraud patterns."""
        patterns: list[SuspiciousSequence] = []
        first_t = _ensure_utc(episode_txs[0].occurred_at)
        last_t = _ensure_utc(episode_txs[-1].occurred_at)
        duration_s = max(0.1, (last_t - first_t).total_seconds())

        # Rolling features at episode peak
        rolling_peak = self.compute_rolling_windows(episode_txs, last_t)
        sub_events = [event_map[t.id] for t in episode_txs if t.id in event_map]
        total_amount = sum(float(t.amount) for t in episode_txs)
        count = len(episode_txs)

        # Compute inter-arrival deltas within episode
        deltas = [
            (_ensure_utc(episode_txs[k].occurred_at) - _ensure_utc(episode_txs[k - 1].occurred_at)).total_seconds()
            for k in range(1, len(episode_txs))
        ]
        min_delta = min(deltas) if deltas else 9999.0
        avg_delta = (sum(deltas) / len(deltas)) if deltas else 9999.0

        # -------------------------------------------------------------
        # PATTERN 1: TRANSACTION_BURST
        # -------------------------------------------------------------
        # Velocity burst: >= 3 transactions in < 30s or >= 4 in < 300s, or delta < 5s
        is_burst = (
            (count >= 3 and duration_s <= 30.0)
            or (count >= 4 and duration_s <= 300.0 and min_delta <= 10.0)
            or (count >= 5 and avg_delta <= 20.0)
        )
        if is_burst:
            # Dynamic comparison vs user baseline
            velocity_multiplier = (count / max(0.1, duration_s / 86400.0)) / max(1.0, baseline_daily_freq)
            severity = (
                "CRITICAL"
                if (velocity_multiplier >= 50.0 or min_delta <= 2.0)
                else "HIGH"
                if (velocity_multiplier >= 15.0 or duration_s <= 30.0 or min_delta <= 5.0)
                else "MEDIUM"
            )
            risk_score = min(98.0, 60.0 + min(35.0, count * 6.0 + (10.0 / max(0.5, min_delta))))

            # Tag events
            for e in sub_events:
                if e.time_since_previous_seconds is not None and e.time_since_previous_seconds <= 15.0:
                    e.risk_signals.append(f"BURST_INTERVAL_{e.time_since_previous_seconds:.1f}S")

            patterns.append(
                SuspiciousSequence(
                    sequence_id=f"seq-burst-{uuid4().hex[:8]}",
                    user_id=user.id,
                    user_email=user.email,
                    pattern_type="TRANSACTION_BURST",
                    pattern_title="Transaction Velocity Burst",
                    severity=severity,
                    risk_score=round(risk_score, 1),
                    start_time=first_t,
                    end_time=last_t,
                    duration_seconds=round(duration_s, 2),
                    duration_formatted=_format_duration(duration_s),
                    transaction_count=count,
                    total_amount=round(total_amount, 2),
                    events=sub_events,
                    rolling_features_at_peak=rolling_peak,
                    explanation=f"Rapid cluster of {count} transactions initiated within {_format_duration(duration_s)} (min interval: {min_delta:.1f}s). Velocity is {velocity_multiplier:.1f}x higher than user daily baseline ({baseline_daily_freq:.1f}/day).",
                    historical_baseline_comparison={
                        "baseline_daily_frequency": baseline_daily_freq,
                        "episode_velocity_ratio": round(velocity_multiplier, 1),
                        "shortest_interval_seconds": round(min_delta, 2),
                    },
                )
            )

        # -------------------------------------------------------------
        # PATTERN 2: RAPID_REPEATED_PAYMENTS
        # -------------------------------------------------------------
        # Duplicate amounts within < 5 minutes (300s)
        amounts = [round(float(t.amount), 2) for t in episode_txs]
        amt_counter = Counter(amounts)
        repeated_groups = {amt: cnt for amt, cnt in amt_counter.items() if cnt >= 2}

        if repeated_groups and duration_s <= 600.0:
            rep_amt, rep_count = max(repeated_groups.items(), key=lambda item: item[1])
            if rep_count >= 2:
                # Tag events with repeated amounts
                for e in sub_events:
                    if round(e.amount, 2) == rep_amt:
                        e.risk_signals.append(f"REPEATED_AMOUNT_${rep_amt:.2f}")

                severity = "HIGH" if rep_count >= 3 or duration_s <= 60.0 else "MEDIUM"
                risk_score = min(95.0, 55.0 + rep_count * 12.0)
                patterns.append(
                    SuspiciousSequence(
                        sequence_id=f"seq-repeat-{uuid4().hex[:8]}",
                        user_id=user.id,
                        user_email=user.email,
                        pattern_type="RAPID_REPEATED_PAYMENTS",
                        pattern_title="Rapid Repeated Payments",
                        severity=severity,
                        risk_score=round(risk_score, 1),
                        start_time=first_t,
                        end_time=last_t,
                        duration_seconds=round(duration_s, 2),
                        duration_formatted=_format_duration(duration_s),
                        transaction_count=count,
                        total_amount=round(total_amount, 2),
                        events=sub_events,
                        rolling_features_at_peak=rolling_peak,
                        explanation=f"Identical amount of ${rep_amt:.2f} was charged {rep_count} times in {_format_duration(duration_s)}, indicating automated bot retries or unauthorized replay charges.",
                        historical_baseline_comparison={
                            "repeated_amount": rep_amt,
                            "repetition_count": rep_count,
                            "window_seconds": round(duration_s, 1),
                        },
                    )
                )

        # -------------------------------------------------------------
        # PATTERN 3: CARD_TESTING
        # -------------------------------------------------------------
        # Micro-amount probes (< $5.00 or < 15% of historical baseline average)
        # especially with failed/declined attempts
        low_value_count = sum(1 for a in amounts if a <= 5.0 or a <= max(1.0, baseline_min_amt * 0.5))
        failed_count = sum(
            1 for t in episode_txs
            if (t.status or "").lower() in ("failed", "blocked", "declined", "rejected", "error")
        )
        is_card_testing = (
            (low_value_count >= 2 and duration_s <= 900.0)
            or (low_value_count >= 1 and failed_count >= 1 and duration_s <= 600.0)
        )
        if is_card_testing and (low_value_count / max(1, count) >= 0.5 or failed_count >= 1):
            for e in sub_events:
                if e.amount <= 5.0 or e.amount <= max(1.0, baseline_min_amt * 0.5):
                    e.risk_signals.append(f"CARD_TEST_PROBE_${e.amount:.2f}")
                if (e.status or "").lower() in ("failed", "blocked", "declined"):
                    e.risk_signals.append("AUTH_FAILURE")

            severity = "CRITICAL" if failed_count >= 2 or low_value_count >= 3 else "HIGH"
            risk_score = min(96.0, 65.0 + low_value_count * 8.0 + failed_count * 10.0)
            patterns.append(
                SuspiciousSequence(
                    sequence_id=f"seq-testing-{uuid4().hex[:8]}",
                    user_id=user.id,
                    user_email=user.email,
                    pattern_type="CARD_TESTING",
                    pattern_title="Card Testing Sequence",
                    severity=severity,
                    risk_score=round(risk_score, 1),
                    start_time=first_t,
                    end_time=last_t,
                    duration_seconds=round(duration_s, 2),
                    duration_formatted=_format_duration(duration_s),
                    transaction_count=count,
                    total_amount=round(total_amount, 2),
                    events=sub_events,
                    rolling_features_at_peak=rolling_peak,
                    explanation=f"Series of {low_value_count} micro-amount probe transactions ({failed_count} declines) executed in {_format_duration(duration_s)}. Typical spend for this account is ${baseline_avg_amt:.2f}.",
                    historical_baseline_comparison={
                        "baseline_average_amount": baseline_avg_amt,
                        "micro_probe_count": low_value_count,
                        "declined_attempts": failed_count,
                    },
                )
            )

        # -------------------------------------------------------------
        # PATTERN 4: SPENDING_ACCELERATION
        # -------------------------------------------------------------
        # Rapid capital drain: episode spend is multiple times the normal daily spend
        expected_window_spend = (baseline_avg_amt * baseline_daily_freq) * (max(60.0, duration_s) / 86400.0)
        spend_acceleration_ratio = total_amount / max(10.0, expected_window_spend)

        if total_amount >= 500.0 and spend_acceleration_ratio >= 10.0 and duration_s <= 1800.0:
            for e in sub_events:
                if e.amount >= baseline_avg_amt * 2.0:
                    e.risk_signals.append(f"ACCELERATED_SPEND_${e.amount:.2f}")

            severity = "CRITICAL" if spend_acceleration_ratio > 30.0 or total_amount > 2500.0 else "HIGH"
            risk_score = min(97.0, 60.0 + min(35.0, spend_acceleration_ratio * 1.5))
            patterns.append(
                SuspiciousSequence(
                    sequence_id=f"seq-accel-{uuid4().hex[:8]}",
                    user_id=user.id,
                    user_email=user.email,
                    pattern_type="SPENDING_ACCELERATION",
                    pattern_title="Sudden Spending Acceleration",
                    severity=severity,
                    risk_score=round(risk_score, 1),
                    start_time=first_t,
                    end_time=last_t,
                    duration_seconds=round(duration_s, 2),
                    duration_formatted=_format_duration(duration_s),
                    transaction_count=count,
                    total_amount=round(total_amount, 2),
                    events=sub_events,
                    rolling_features_at_peak=rolling_peak,
                    explanation=f"Sudden spending acceleration: ${total_amount:.2f} spent in {_format_duration(duration_s)}, exceeding baseline expected rate by {spend_acceleration_ratio:.1f}x (user normal daily spend: ${baseline_avg_amt * baseline_daily_freq:.2f}/day).",
                    historical_baseline_comparison={
                        "baseline_daily_spend": round(baseline_avg_amt * baseline_daily_freq, 2),
                        "spend_acceleration_ratio": round(spend_acceleration_ratio, 1),
                    },
                )
            )

        # -------------------------------------------------------------
        # PATTERN 5: MULTIPLE_MERCHANTS_RAPID
        # -------------------------------------------------------------
        # Merchant hopping: >= 3 distinct merchants in < 300s (5m) or >= 4 in < 1800s (30m)
        distinct_merchants = {
            str(t.merchant_id) if t.merchant_id else t.merchant_category
            for t in episode_txs
            if t.merchant_id or t.merchant_category
        }
        distinct_m_count = len(distinct_merchants)

        is_merchant_hopping = (
            (distinct_m_count >= 3 and duration_s <= 300.0)
            or (distinct_m_count >= 4 and duration_s <= 1800.0)
        )
        if is_merchant_hopping:
            for e in sub_events:
                e.risk_signals.append(f"MULTI_MERCHANT_{e.merchant_category or 'GENERAL'}")

            severity = "CRITICAL" if distinct_m_count >= 4 and duration_s <= 180.0 else "HIGH" if distinct_m_count >= 3 else "MEDIUM"
            risk_score = min(94.0, 58.0 + distinct_m_count * 8.0)
            patterns.append(
                SuspiciousSequence(
                    sequence_id=f"seq-merchant-{uuid4().hex[:8]}",
                    user_id=user.id,
                    user_email=user.email,
                    pattern_type="MULTIPLE_MERCHANTS_RAPID",
                    pattern_title="Multiple Merchants in Short Period",
                    severity=severity,
                    risk_score=round(risk_score, 1),
                    start_time=first_t,
                    end_time=last_t,
                    duration_seconds=round(duration_s, 2),
                    duration_formatted=_format_duration(duration_s),
                    transaction_count=count,
                    total_amount=round(total_amount, 2),
                    events=sub_events,
                    rolling_features_at_peak=rolling_peak,
                    explanation=f"Purchases executed across {distinct_m_count} different merchants within {_format_duration(duration_s)}, characteristic of compromised credential liquidation or coordinated scraping.",
                    historical_baseline_comparison={
                        "distinct_merchant_count": distinct_m_count,
                        "time_span_seconds": round(duration_s, 1),
                    },
                )
            )

        return patterns

    def get_transaction_temporal_context(
        self,
        transaction_id: UUID,
    ) -> TransactionTemporalContextResponse:
        """Fetch surrounding temporal context and rolling windows for a specific transaction."""
        target_tx = self.db.scalar(select(Transaction).where(Transaction.id == transaction_id))
        if not target_tx:
            raise ValueError(f"Transaction {transaction_id} not found")

        user_id = target_tx.user_id
        target_time = _ensure_utc(target_tx.occurred_at)

        # Retrieve user transactions within +/- 2 hours
        window_start = target_time - timedelta(hours=2)
        window_end = target_time + timedelta(hours=2)

        surrounding_txs = list(
            self.db.scalars(
                select(Transaction)
                .where(
                    Transaction.user_id == user_id,
                    Transaction.occurred_at >= window_start,
                    Transaction.occurred_at <= window_end,
                )
                .order_by(Transaction.occurred_at.asc())
            ).all()
        )

        rolling = self.compute_rolling_windows(surrounding_txs, target_time)

        # Separate into preceding and succeeding
        preceding: list[TemporalSequenceEvent] = []
        succeeding: list[TemporalSequenceEvent] = []

        all_txs_sorted = sorted(surrounding_txs, key=lambda t: _ensure_utc(t.occurred_at))
        target_idx = next((idx for idx, t in enumerate(all_txs_sorted) if t.id == transaction_id), -1)

        for i, tx in enumerate(all_txs_sorted):
            prev = all_txs_sorted[i - 1] if i > 0 else None
            dt = (_ensure_utc(tx.occurred_at) - _ensure_utc(prev.occurred_at)).total_seconds() if prev else None
            dt_fmt = _format_duration(dt) if dt is not None else "Start"

            dev_fp = None
            if tx.metadata_json and isinstance(tx.metadata_json, dict):
                dev_fp = tx.metadata_json.get("device_fingerprint")

            ev = TemporalSequenceEvent(
                transaction_id=tx.id,
                timestamp=tx.occurred_at,
                time_since_previous_seconds=round(dt, 2) if dt is not None else None,
                time_since_previous_formatted=dt_fmt,
                amount=float(tx.amount),
                currency=tx.currency,
                location=tx.location,
                device=dev_fp or (str(tx.device_id) if tx.device_id else None),
                ip_address=tx.ip_address,
                merchant=tx.metadata_json.get("merchant") if tx.metadata_json else None,
                merchant_category=tx.merchant_category,
                status=tx.status,
                is_fraud=tx.is_fraud,
                risk_signals=[],
            )
            if i < target_idx:
                preceding.append(ev)
            elif i > target_idx:
                succeeding.append(ev)

        # Delta-t for target
        target_dt = None
        if target_idx > 0:
            target_dt = (_ensure_utc(target_tx.occurred_at) - _ensure_utc(all_txs_sorted[target_idx - 1].occurred_at)).total_seconds()
        target_dt_fmt = _format_duration(target_dt) if target_dt is not None else "Initial"

        # Check triggered patterns at this point
        patterns_detected: list[str] = []
        if rolling.window_30s.transaction_count >= 3:
            patterns_detected.append("TRANSACTION_BURST_30S")
        if rolling.window_5m.repeated_amounts_count >= 2:
            patterns_detected.append("RAPID_REPEATED_PAYMENT")
        if rolling.window_5m.unique_merchants >= 3:
            patterns_detected.append("MULTIPLE_MERCHANTS_5M")
        if rolling.window_5m.failed_attempts >= 2:
            patterns_detected.append("CARD_TESTING_SUSPECT")

        return TransactionTemporalContextResponse(
            transaction_id=target_tx.id,
            occurred_at=target_tx.occurred_at,
            rolling_windows=rolling,
            preceding_events=preceding[-5:],
            succeeding_events=succeeding[:5],
            triggered_patterns=patterns_detected,
            time_since_previous_seconds=round(target_dt, 2) if target_dt is not None else None,
            time_since_previous_formatted=target_dt_fmt,
        )

    def scan_system_suspicious_sequences(
        self,
        pattern_type: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[SuspiciousSequence]:
        """Scan across accounts to detect and aggregate all suspicious sequences."""
        users = list(self.db.scalars(select(User).limit(limit)).all())
        all_seqs: list[SuspiciousSequence] = []

        for user in users:
            try:
                res = self.analyze_user_sequences(user.id)
                for s in res.detected_sequences:
                    if pattern_type and s.pattern_type != pattern_type:
                        continue
                    if severity and s.severity != severity:
                        continue
                    all_seqs.append(s)
            except Exception:
                continue

        # Sort sequences by severity then start time
        severity_map = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        all_seqs.sort(key=lambda s: (severity_map.get(s.severity, 4), s.start_time), reverse=False)
        return all_seqs[:limit]
