"""User Behavioral Intelligence Engine.

Calculates per-user historical behavioral baselines, rolling window statistics,
and multi-dimensional deviation metrics for transaction evaluation.

CRITICAL GUARANTEE:
Strict lookahead-free evaluation. The current transaction being evaluated is NEVER
included in the historical dataset used to compute its own baseline.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
import statistics
from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Transaction, User
from app.schemas.behavior import (
    BehavioralBaseline,
    CurrentActivity,
    DayOfWeekActivity,
    DeviationAnalysis,
    DeviationMetric,
    DistributionBucket,
    HourlyActivity,
    RiskIndicator,
    TimelinePoint,
    UserBehaviorProfileResponse,
    UserProfileSummary,
)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MIN_HISTORY_THRESHOLD = 5


def _ensure_utc(dt: datetime | None) -> datetime:
    """Normalize datetime to timezone-aware UTC to prevent naive/aware subtraction errors."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class BehaviorEngine:
    """Engine for computing behavioral baselines and deviation metrics."""

    def __init__(
        self,
        db: Session,
        baseline_window_days: int = 90,
        recent_window_days: int = 30,
        min_history_threshold: int = MIN_HISTORY_THRESHOLD,
    ):
        self.db = db
        self.baseline_window_days = baseline_window_days
        self.recent_window_days = recent_window_days
        self.min_history_threshold = min_history_threshold

    def get_user_behavior_profile(
        self,
        user_id: UUID,
        current_transaction_id: UUID | None = None,
    ) -> UserBehaviorProfileResponse:
        """Compute full behavioral profile, baselines, and deviations for a user."""
        user = self.db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise ValueError(f"User with ID {user_id} not found")

        # Determine reference transaction and reference time
        current_tx: Transaction | None = None
        if current_transaction_id:
            current_tx = self.db.scalar(
                select(Transaction).where(
                    Transaction.id == current_transaction_id,
                    Transaction.user_id == user_id,
                )
            )
            if not current_tx:
                raise ValueError(
                    f"Transaction {current_transaction_id} not found for user {user_id}"
                )
        else:
            # Pick latest transaction of the user as current activity
            current_tx = self.db.scalars(
                select(Transaction)
                .where(Transaction.user_id == user_id)
                .order_by(Transaction.occurred_at.desc())
                .limit(1)
            ).first()

        reference_time = (
            current_tx.occurred_at
            if current_tx
            else datetime.now(timezone.utc)
        )

        # 1. Fetch strictly prior transactions for the baseline
        # CRITICAL: current_tx is excluded via id != current_tx.id and future transactions excluded via <= reference_time
        query = (
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.occurred_at <= reference_time,
            )
        )
        if current_tx:
            query = query.where(Transaction.id != current_tx.id)

        # Apply baseline window limit if configured
        if self.baseline_window_days > 0:
            window_start = _ensure_utc(reference_time) - timedelta(days=self.baseline_window_days)
            query = query.where(Transaction.occurred_at >= window_start)

        query = query.order_by(Transaction.occurred_at.asc())
        history: list[Transaction] = list(self.db.scalars(query).all())

        # Also get lifetime stats for account
        lifetime_query = select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.occurred_at <= reference_time,
        )
        if current_tx:
            lifetime_query = lifetime_query.where(Transaction.id != current_tx.id)
        lifetime_history: list[Transaction] = list(self.db.scalars(lifetime_query).all())

        # 2. Compute baseline statistics
        baseline = self._compute_baseline(user_id, history, lifetime_history, reference_time)

        # 3. Compute current activity & deviations if a current transaction exists
        curr_activity: CurrentActivity | None = None
        deviation_analysis: DeviationAnalysis | None = None
        risk_indicators: list[RiskIndicator] = []

        if current_tx:
            curr_activity = self._build_current_activity(current_tx, history, reference_time)
            deviation_analysis, risk_indicators = self._compute_deviations(
                current_tx,
                baseline,
                history,
                reference_time,
            )

        # 4. Build recent activity sequence (e.g. up to 10 most recent transactions)
        recent_txs = sorted(
            history + ([current_tx] if current_tx else []),
            key=lambda t: _ensure_utc(t.occurred_at),
            reverse=True,
        )[:10]
        recent_activity_list = [
            self._build_current_activity(t, history, t.occurred_at)
            for t in recent_txs
        ]

        # 5. Build timeline points (up to 25 historical points)
        timeline = self._build_timeline(history, baseline, current_tx)

        # Calculate account age in days
        account_age_days: int | None = None
        if user.created_at:
            account_age_days = max(
                0, (_ensure_utc(reference_time) - _ensure_utc(user.created_at)).days
            )

        return UserBehaviorProfileResponse(
            user_id=user.id,
            user_email=user.email,
            user_display_name=user.display_name,
            account_age_days=account_age_days,
            behavioral_baseline=baseline,
            current_activity=curr_activity,
            current_deviation=deviation_analysis,
            risk_indicators=risk_indicators,
            recent_activity=recent_activity_list,
            behavior_timeline=timeline,
        )

    def _compute_baseline(
        self,
        user_id: UUID,
        history: list[Transaction],
        lifetime_history: list[Transaction],
        reference_time: datetime,
    ) -> BehavioralBaseline:
        """Compute statistical baselines strictly on historical transactions."""
        count = len(history)
        has_sufficient = count >= self.min_history_threshold

        if count == 0:
            return BehavioralBaseline(
                user_id=user_id,
                calculated_at=reference_time,
                baseline_window_days=self.baseline_window_days,
                historical_transaction_count=0,
                has_sufficient_history=False,
                average_transaction_amount=0.0,
                median_transaction_amount=0.0,
                standard_deviation=0.0,
                min_transaction_amount=0.0,
                max_transaction_amount=0.0,
                typical_amount_range=[0.0, 0.0],
                average_daily_frequency=0.0,
                burstiness_baseline=0.0,
                failed_transaction_count=0,
                historical_fraud_association=0,
                hourly_distribution=[HourlyActivity(hour=h, count=0, percentage=0.0) for h in range(24)],
                day_of_week_distribution=[
                    DayOfWeekActivity(day=d, day_name=DAY_NAMES[d], count=0, percentage=0.0)
                    for d in range(7)
                ],
                frequent_locations=[],
                frequent_merchant_categories=[],
                known_devices=[],
                known_ip_addresses=[],
            )

        amounts = [float(t.amount) for t in history]
        avg_amt = statistics.mean(amounts)
        med_amt = statistics.median(amounts)
        std_amt = statistics.stdev(amounts) if count > 1 else 0.0
        min_amt = min(amounts)
        max_amt = max(amounts)

        typical_lower = max(0.0, round(avg_amt - 1.5 * std_amt, 2))
        typical_upper = round(avg_amt + 1.5 * std_amt, 2)

        # Temporal spans and frequency
        first_time = _ensure_utc(history[0].occurred_at)
        last_time = _ensure_utc(history[-1].occurred_at)
        span_days = max(1.0, (last_time - first_time).total_seconds() / 86400.0)
        daily_freq = round(count / span_days, 2)

        # Baseline burstiness: coefficient of variation of inter-arrival times
        burstiness_val = self._calculate_burstiness(history)

        # Failure and fraud counts
        failed_count = sum(
            1 for t in lifetime_history
            if (t.status or "").lower() in ("failed", "blocked", "declined", "rejected", "error")
        )
        fraud_count = sum(1 for t in lifetime_history if t.is_fraud)

        # Hourly distribution (0 - 23)
        hour_counts = Counter(t.occurred_at.hour for t in history)
        hourly_dist = [
            HourlyActivity(
                hour=h,
                count=hour_counts.get(h, 0),
                percentage=round((hour_counts.get(h, 0) / count) * 100.0, 1),
            )
            for h in range(24)
        ]

        # Day of week distribution (0 = Mon, 6 = Sun)
        dow_counts = Counter(t.occurred_at.weekday() for t in history)
        dow_dist = [
            DayOfWeekActivity(
                day=d,
                day_name=DAY_NAMES[d],
                count=dow_counts.get(d, 0),
                percentage=round((dow_counts.get(d, 0) / count) * 100.0, 1),
            )
            for d in range(7)
        ]

        # Frequent locations
        loc_counts = Counter(t.location for t in history if t.location)
        loc_dist = [
            DistributionBucket(
                key=loc,
                count=c,
                percentage=round((c / count) * 100.0, 1),
            )
            for loc, c in loc_counts.most_common(10)
        ]

        # Frequent merchant categories
        cat_counts = Counter(t.merchant_category for t in history if t.merchant_category)
        cat_dist = [
            DistributionBucket(
                key=cat,
                count=c,
                percentage=round((c / count) * 100.0, 1),
            )
            for cat, c in cat_counts.most_common(10)
        ]

        # Known devices & IPs (from lifetime history)
        known_devices = sorted(
            list({
                str(t.device_id) if t.device_id else t.metadata_json.get("device_fingerprint")
                for t in lifetime_history
                if t.device_id or (t.metadata_json and t.metadata_json.get("device_fingerprint"))
            })
        )
        known_ips = sorted(list({t.ip_address for t in lifetime_history if t.ip_address}))

        return BehavioralBaseline(
            user_id=user_id,
            calculated_at=reference_time,
            baseline_window_days=self.baseline_window_days,
            historical_transaction_count=count,
            has_sufficient_history=has_sufficient,
            average_transaction_amount=round(avg_amt, 2),
            median_transaction_amount=round(med_amt, 2),
            standard_deviation=round(std_amt, 2),
            min_transaction_amount=round(min_amt, 2),
            max_transaction_amount=round(max_amt, 2),
            typical_amount_range=[typical_lower, typical_upper],
            average_daily_frequency=daily_freq,
            burstiness_baseline=round(burstiness_val, 3),
            failed_transaction_count=failed_count,
            historical_fraud_association=fraud_count,
            hourly_distribution=hourly_dist,
            day_of_week_distribution=dow_dist,
            frequent_locations=loc_dist,
            frequent_merchant_categories=cat_dist,
            known_devices=known_devices,
            known_ip_addresses=known_ips,
        )

    def _build_current_activity(
        self,
        current_tx: Transaction,
        history: list[Transaction],
        reference_time: datetime,
    ) -> CurrentActivity:
        """Extract telemetry and rolling counts for the current transaction."""
        ref_utc = _ensure_utc(reference_time)
        window_30d = ref_utc - timedelta(days=30)
        window_24h = ref_utc - timedelta(hours=24)

        recent_30d = [t for t in history if _ensure_utc(t.occurred_at) >= window_30d]
        recent_24h = [t for t in history if _ensure_utc(t.occurred_at) >= window_24h]

        burstiness_24h = self._calculate_burstiness(recent_24h + [current_tx])

        device_fp = None
        if current_tx.metadata_json and isinstance(current_tx.metadata_json, dict):
            device_fp = current_tx.metadata_json.get("device_fingerprint")

        return CurrentActivity(
            transaction_id=current_tx.id,
            occurred_at=current_tx.occurred_at,
            amount=float(current_tx.amount),
            currency=current_tx.currency,
            merchant_category=current_tx.merchant_category,
            location=current_tx.location,
            device_id=current_tx.device_id,
            device_fingerprint=device_fp,
            ip_address=current_tx.ip_address,
            payment_method=current_tx.payment_method,
            status=current_tx.status,
            recent_transaction_count_30d=len(recent_30d) + 1,
            recent_transaction_count_24h=len(recent_24h) + 1,
            recent_burstiness=round(burstiness_24h, 3),
        )

    def _compute_deviations(
        self,
        current_tx: Transaction,
        baseline: BehavioralBaseline,
        history: list[Transaction],
        reference_time: datetime,
    ) -> tuple[DeviationAnalysis, list[RiskIndicator]]:
        """Compute deviations between current transaction and the historical baseline."""
        risk_indicators: list[RiskIndicator] = []
        is_sufficient = baseline.has_sufficient_history
        current_amount = float(current_tx.amount)

        # 1. Amount deviation
        if not is_sufficient:
            amt_dev = DeviationMetric(
                name="amount_deviation",
                label="Amount deviation",
                value=0.0,
                score=0.1,
                level="insufficient_history",
                explanation="Insufficient prior transactions to establish amount baseline.",
            )
        else:
            mean = baseline.average_transaction_amount
            std = baseline.standard_deviation
            if std > 0.01:
                z_score = abs(current_amount - mean) / std
            else:
                z_score = abs(current_amount - mean) / (mean + 1.0)

            # Score 0.0 to 1.0
            amt_score = min(1.0, z_score / 4.0)
            if z_score < 1.5:
                amt_level = "normal"
                amt_desc = f"Amount ${current_amount:.2f} is within normal range (${baseline.typical_amount_range[0]:.2f} - ${baseline.typical_amount_range[1]:.2f})."
            elif z_score < 3.0:
                amt_level = "moderate"
                amt_desc = f"Amount ${current_amount:.2f} is moderately elevated ({z_score:.1f}σ above mean ${mean:.2f})."
            elif z_score < 5.0:
                amt_level = "high"
                amt_desc = f"Amount ${current_amount:.2f} is significantly elevated ({z_score:.1f}σ above mean ${mean:.2f})."
                risk_indicators.append(
                    RiskIndicator(
                        code="AMOUNT_SPIKE",
                        title="Unusual Transaction Amount",
                        severity="medium",
                        description=f"Transaction amount of ${current_amount:.2f} deviates {z_score:.1f}σ from user historical average of ${mean:.2f}.",
                    )
                )
            else:
                amt_level = "extreme"
                amt_desc = f"Amount ${current_amount:.2f} is extreme ({z_score:.1f}σ above mean ${mean:.2f})."
                risk_indicators.append(
                    RiskIndicator(
                        code="EXTREME_AMOUNT",
                        title="Extreme Amount Outlier",
                        severity="high",
                        description=f"Amount of ${current_amount:.2f} is {z_score:.1f}σ higher than typical user spend.",
                    )
                )

            amt_dev = DeviationMetric(
                name="amount_deviation",
                label="Amount deviation",
                value=round(z_score, 2),
                score=round(amt_score, 3),
                level=amt_level,
                explanation=amt_desc,
            )

        # 2. Transaction frequency deviation
        window_24h = _ensure_utc(reference_time) - timedelta(hours=24)
        recent_24h_count = sum(1 for t in history if _ensure_utc(t.occurred_at) >= window_24h) + 1  # includes current
        baseline_daily = baseline.average_daily_frequency
        if not is_sufficient or baseline_daily <= 0:
            freq_dev = DeviationMetric(
                name="transaction_frequency_deviation",
                label="Transaction frequency deviation",
                value=float(recent_24h_count),
                score=0.1,
                level="insufficient_history",
                explanation=f"{recent_24h_count} transactions in the last 24h.",
            )
        else:
            freq_ratio = recent_24h_count / max(0.5, baseline_daily)
            freq_score = min(1.0, max(0.0, (freq_ratio - 1.0) / 4.0))
            if freq_ratio < 2.0:
                freq_level = "normal"
                freq_desc = f"24h velocity ({recent_24h_count}) is consistent with average daily volume ({baseline_daily:.1f}/day)."
            elif freq_ratio < 4.0:
                freq_level = "moderate"
                freq_desc = f"24h velocity ({recent_24h_count}) is {freq_ratio:.1f}x higher than average daily volume ({baseline_daily:.1f}/day)."
            else:
                freq_level = "high"
                freq_desc = f"24h velocity ({recent_24h_count}) is {freq_ratio:.1f}x normal daily frequency."
                risk_indicators.append(
                    RiskIndicator(
                        code="VELOCITY_SPIKE",
                        title="High Transaction Velocity",
                        severity="medium",
                        description=f"User initiated {recent_24h_count} transactions in 24h, {freq_ratio:.1f}x the baseline average.",
                    )
                )

            freq_dev = DeviationMetric(
                name="transaction_frequency_deviation",
                label="Transaction frequency deviation",
                value=round(freq_ratio, 2),
                score=round(freq_score, 3),
                level=freq_level,
                explanation=freq_desc,
            )

        # 3. Time-of-day deviation
        curr_hour = current_tx.occurred_at.hour
        hour_stat = next((h for h in baseline.hourly_distribution if h.hour == curr_hour), None)
        if not is_sufficient:
            tod_dev = DeviationMetric(
                name="time_of_day_deviation",
                label="Time-of-day deviation",
                value=float(curr_hour),
                score=0.1,
                level="insufficient_history",
                explanation=f"Transaction at {curr_hour:02d}:00.",
            )
        else:
            hour_pct = (hour_stat.percentage / 100.0) if hour_stat else 0.0
            if hour_pct >= 0.08:
                tod_level = "normal"
                tod_score = 0.05
                tod_desc = f"Active hour ({curr_hour:02d}:00 UTC represents {hour_pct*100:.1f}% of historical transactions)."
            elif hour_pct > 0:
                tod_level = "moderate"
                tod_score = 0.45
                tod_desc = f"Less common hour ({curr_hour:02d}:00 UTC represents only {hour_pct*100:.1f}% of activity)."
            else:
                tod_level = "high"
                tod_score = 0.85
                tod_desc = f"Unusual hour: Account has never transacted at {curr_hour:02d}:00 UTC in baseline window."
                risk_indicators.append(
                    RiskIndicator(
                        code="UNUSUAL_HOUR",
                        title="Unusual Time of Day",
                        severity="low",
                        description=f"Transaction initiated at {curr_hour:02d}:00 UTC, an inactive window for this account.",
                    )
                )

            tod_dev = DeviationMetric(
                name="time_of_day_deviation",
                label="Time-of-day deviation",
                value=round(1.0 - hour_pct, 2),
                score=round(tod_score, 3),
                level=tod_level,
                explanation=tod_desc,
            )

        # 4. Day-of-week deviation
        curr_dow = current_tx.occurred_at.weekday()
        dow_stat = next((d for d in baseline.day_of_week_distribution if d.day == curr_dow), None)
        if not is_sufficient:
            dow_dev = DeviationMetric(
                name="day_of_week_deviation",
                label="Day-of-week deviation",
                value=float(curr_dow),
                score=0.1,
                level="insufficient_history",
                explanation=f"Transaction on {DAY_NAMES[curr_dow]}.",
            )
        else:
            dow_pct = (dow_stat.percentage / 100.0) if dow_stat else 0.0
            if dow_pct >= 0.10:
                dow_level = "normal"
                dow_score = 0.05
                dow_desc = f"Normal day: {DAY_NAMES[curr_dow]} accounts for {dow_pct*100:.1f}% of activity."
            elif dow_pct > 0:
                dow_level = "moderate"
                dow_score = 0.40
                dow_desc = f"Low-frequency day: {DAY_NAMES[curr_dow]} accounts for {dow_pct*100:.1f}% of activity."
            else:
                dow_level = "high"
                dow_score = 0.80
                dow_desc = f"Unseen weekday: Account has never transacted on a {DAY_NAMES[curr_dow]}."

            dow_dev = DeviationMetric(
                name="day_of_week_deviation",
                label="Day-of-week deviation",
                value=round(1.0 - dow_pct, 2),
                score=round(dow_score, 3),
                level=dow_level,
                explanation=dow_desc,
            )

        # 5. Location deviation
        curr_loc = current_tx.location
        if not curr_loc:
            loc_dev = DeviationMetric(
                name="location_deviation",
                label="Location deviation",
                value=0.0,
                score=0.0,
                level="normal",
                explanation="No geographic telemetry recorded for this transaction.",
            )
        elif not is_sufficient:
            loc_dev = DeviationMetric(
                name="location_deviation",
                label="Location deviation",
                value=0.0,
                score=0.1,
                level="insufficient_history",
                explanation=f"Location '{curr_loc}' (limited history).",
            )
        else:
            matched_loc = next((l for l in baseline.frequent_locations if l.key.lower() == curr_loc.lower()), None)
            if matched_loc:
                loc_pct = matched_loc.percentage / 100.0
                loc_level = "normal" if loc_pct > 0.2 else "moderate"
                loc_score = max(0.05, 1.0 - loc_pct)
                loc_desc = f"Recognized location '{curr_loc}' represents {matched_loc.percentage:.1f}% of user transactions."
            else:
                loc_level = "high"
                loc_score = 0.90
                loc_desc = f"Novel location '{curr_loc}' has never been observed in baseline history."
                risk_indicators.append(
                    RiskIndicator(
                        code="NEW_LOCATION",
                        title="Unrecognized Location",
                        severity="medium",
                        description=f"Transaction originated from '{curr_loc}', where this user has no prior history.",
                    )
                )

            loc_dev = DeviationMetric(
                name="location_deviation",
                label="Location deviation",
                value=1.0 if not matched_loc else round(1.0 - (matched_loc.percentage / 100.0), 2),
                score=round(loc_score, 3),
                level=loc_level,
                explanation=loc_desc,
            )

        # 6. Merchant category deviation
        curr_cat = current_tx.merchant_category
        if not curr_cat:
            cat_dev = DeviationMetric(
                name="merchant_category_deviation",
                label="Merchant category deviation",
                value=0.0,
                score=0.0,
                level="normal",
                explanation="No merchant category metadata provided.",
            )
        elif not is_sufficient:
            cat_dev = DeviationMetric(
                name="merchant_category_deviation",
                label="Merchant category deviation",
                value=0.0,
                score=0.1,
                level="insufficient_history",
                explanation=f"Merchant category '{curr_cat}'.",
            )
        else:
            matched_cat = next((c for c in baseline.frequent_merchant_categories if c.key.lower() == curr_cat.lower()), None)
            if matched_cat:
                cat_pct = matched_cat.percentage / 100.0
                cat_level = "normal" if cat_pct > 0.15 else "moderate"
                cat_score = max(0.05, 1.0 - cat_pct)
                cat_desc = f"Category '{curr_cat}' represents {matched_cat.percentage:.1f}% of historical spend."
            else:
                cat_level = "moderate"
                cat_score = 0.70
                cat_desc = f"Novel merchant category '{curr_cat}' not previously frequented by user."

            cat_dev = DeviationMetric(
                name="merchant_category_deviation",
                label="Merchant category deviation",
                value=1.0 if not matched_cat else round(1.0 - (matched_cat.percentage / 100.0), 2),
                score=round(cat_score, 3),
                level=cat_level,
                explanation=cat_desc,
            )

        # 7. Device novelty
        device_id_str = str(current_tx.device_id) if current_tx.device_id else None
        device_fp = (
            current_tx.metadata_json.get("device_fingerprint")
            if current_tx.metadata_json and isinstance(current_tx.metadata_json, dict)
            else None
        )
        is_known_device = False
        if device_id_str and device_id_str in baseline.known_devices:
            is_known_device = True
        elif device_fp and device_fp in baseline.known_devices:
            is_known_device = True

        if not device_id_str and not device_fp:
            dev_novelty = DeviationMetric(
                name="device_novelty",
                label="Device novelty",
                value=0.0,
                score=0.2,
                level="moderate",
                explanation="No device telemetry captured.",
            )
        elif not is_sufficient:
            dev_novelty = DeviationMetric(
                name="device_novelty",
                label="Device novelty",
                value=0.0 if is_known_device else 1.0,
                score=0.3 if not is_known_device else 0.0,
                level="insufficient_history",
                explanation="Device seen during early account history.",
            )
        elif is_known_device:
            dev_novelty = DeviationMetric(
                name="device_novelty",
                label="Device novelty",
                value=0.0,
                score=0.0,
                level="normal",
                explanation="Device fingerprint matches user's registered/frequently used hardware.",
            )
        else:
            dev_novelty = DeviationMetric(
                name="device_novelty",
                label="Device novelty",
                value=1.0,
                score=1.0,
                level="high",
                explanation="Unrecognized device: Hardware fingerprint has never been authenticated by this user.",
            )
            risk_indicators.append(
                RiskIndicator(
                    code="NEW_DEVICE",
                    title="Unrecognized Device Authenticated",
                    severity="high",
                    description="Transaction was submitted from a device fingerprint never observed in historical baseline.",
                )
            )

        # 8. IP novelty
        curr_ip = current_tx.ip_address
        if not curr_ip:
            ip_dev = DeviationMetric(
                name="ip_novelty",
                label="IP novelty",
                value=0.0,
                score=0.0,
                level="normal",
                explanation="No IP address logged.",
            )
        elif not is_sufficient:
            ip_dev = DeviationMetric(
                name="ip_novelty",
                label="IP novelty",
                value=0.0,
                score=0.1,
                level="insufficient_history",
                explanation=f"IP {curr_ip}.",
            )
        elif curr_ip in baseline.known_ip_addresses:
            ip_dev = DeviationMetric(
                name="ip_novelty",
                label="IP novelty",
                value=0.0,
                score=0.0,
                level="normal",
                explanation=f"IP address {curr_ip} matches historical access logs.",
            )
        else:
            # Check subnet /24 match
            curr_subnet = ".".join(curr_ip.split(".")[:3]) if "." in curr_ip else curr_ip
            matched_subnet = any(ip.startswith(curr_subnet) for ip in baseline.known_ip_addresses)
            if matched_subnet:
                ip_score = 0.4
                ip_level = "moderate"
                ip_desc = f"Novel IP {curr_ip} resides in known subnet {curr_subnet}.0/24."
            else:
                ip_score = 0.95
                ip_level = "high"
                ip_desc = f"Novel IP {curr_ip} in an unobserved geographic/network block."
                risk_indicators.append(
                    RiskIndicator(
                        code="NEW_IP",
                        title="Novel Network / IP Origin",
                        severity="medium",
                        description=f"Transaction originated from new IP {curr_ip}, completely outside known subnets.",
                    )
                )

            ip_dev = DeviationMetric(
                name="ip_novelty",
                label="IP novelty",
                value=1.0,
                score=round(ip_score, 3),
                level=ip_level,
                explanation=ip_desc,
            )

        # 9. Transaction burstiness
        window_24h = _ensure_utc(reference_time) - timedelta(hours=24)
        recent_txs_for_burst = [t for t in history if _ensure_utc(t.occurred_at) >= window_24h]
        recent_burstiness = self._calculate_burstiness(recent_txs_for_burst + [current_tx])
        burst_diff = max(0.0, recent_burstiness - baseline.burstiness_baseline)
        if not is_sufficient:
            burst_dev = DeviationMetric(
                name="transaction_burstiness",
                label="Transaction burstiness",
                value=round(recent_burstiness, 3),
                score=0.1,
                level="insufficient_history",
                explanation="Insufficient interval history to measure burstiness.",
            )
        elif recent_burstiness > 0.75 and burst_diff > 0.35:
            burst_dev = DeviationMetric(
                name="transaction_burstiness",
                label="Transaction burstiness",
                value=round(recent_burstiness, 3),
                score=0.85,
                level="high",
                explanation=f"Extreme burstiness ({recent_burstiness:.2f}) indicates automated or rapid-fire transactions.",
            )
            risk_indicators.append(
                RiskIndicator(
                    code="BURST_ACTIVITY",
                    title="Transaction Burst Detected",
                    severity="high",
                    description="Multiple transactions in rapid, clustered succession with abnormal interval variance.",
                )
            )
        elif burst_diff > 0.2:
            burst_dev = DeviationMetric(
                name="transaction_burstiness",
                label="Transaction burstiness",
                value=round(recent_burstiness, 3),
                score=0.50,
                level="moderate",
                explanation=f"Elevated temporal clustering ({recent_burstiness:.2f}) compared to baseline ({baseline.burstiness_baseline:.2f}).",
            )
        else:
            burst_dev = DeviationMetric(
                name="transaction_burstiness",
                label="Transaction burstiness",
                value=round(recent_burstiness, 3),
                score=0.10,
                level="normal",
                explanation=f"Interval clustering ({recent_burstiness:.2f}) is within baseline limits.",
            )

        # Check historical fraud association
        if baseline.historical_fraud_association > 0:
            risk_indicators.append(
                RiskIndicator(
                    code="HISTORICAL_FRAUD",
                    title="Prior Fraud Association",
                    severity="high",
                    description=f"Account has {baseline.historical_fraud_association} prior confirmed fraudulent incident(s).",
                )
            )

        # Composite deviation score calculation (weighted blend)
        weights = {
            "device": 0.22,
            "ip": 0.16,
            "amount": 0.24,
            "location": 0.16,
            "time": 0.08,
            "burst": 0.14,
        }
        composite = (
            weights["device"] * dev_novelty.score
            + weights["ip"] * ip_dev.score
            + weights["amount"] * amt_dev.score
            + weights["location"] * loc_dev.score
            + weights["time"] * tod_dev.score
            + weights["burst"] * burst_dev.score
        )
        composite = round(min(1.0, max(0.0, composite)), 3)

        if composite < 0.25:
            overall_risk = "LOW"
        elif composite < 0.60:
            overall_risk = "MEDIUM"
        else:
            overall_risk = "HIGH"

        analysis = DeviationAnalysis(
            amount_deviation=amt_dev,
            transaction_frequency_deviation=freq_dev,
            time_of_day_deviation=tod_dev,
            day_of_week_deviation=dow_dev,
            location_deviation=loc_dev,
            merchant_category_deviation=cat_dev,
            device_novelty=dev_novelty,
            ip_novelty=ip_dev,
            transaction_burstiness=burst_dev,
            composite_deviation_score=composite,
            overall_risk_level=overall_risk,
        )

        return analysis, risk_indicators

    def _build_timeline(
        self,
        history: list[Transaction],
        baseline: BehavioralBaseline,
        current_tx: Transaction | None,
    ) -> list[TimelinePoint]:
        """Construct a point-in-time timeline of deviations across user history."""
        points: list[TimelinePoint] = []
        all_txs = history[-20:] + ([current_tx] if current_tx else [])

        mean = baseline.average_transaction_amount
        std = baseline.standard_deviation

        for tx in all_txs:
            amt = float(tx.amount)
            # Lightweight point-in-time deviation calculation
            if std > 0.01:
                z = abs(amt - mean) / std
            else:
                z = 0.0
            score = min(1.0, z / 4.0)

            # Boost score if device was novel or transaction was flagged fraud
            if tx.is_fraud:
                score = max(score, 0.90)

            points.append(
                TimelinePoint(
                    timestamp=tx.occurred_at,
                    transaction_id=tx.id,
                    amount=amt,
                    location=tx.location,
                    merchant_category=tx.merchant_category,
                    deviation_score=round(score, 3),
                    is_fraud=tx.is_fraud,
                    status=tx.status,
                )
            )

        return points

    def _calculate_burstiness(self, tx_list: Sequence[Transaction]) -> float:
        """Calculate normalized burstiness parameter B in [-1, 1] mapped to [0, 1].

        B = (sigma - mu) / (sigma + mu) where dt are inter-arrival intervals.
        """
        if len(tx_list) < 3:
            return 0.0

        sorted_txs = sorted(tx_list, key=lambda t: _ensure_utc(t.occurred_at))
        intervals = [
            (_ensure_utc(sorted_txs[i].occurred_at) - _ensure_utc(sorted_txs[i - 1].occurred_at)).total_seconds()
            for i in range(1, len(sorted_txs))
        ]
        # Filter out 0 intervals (instantaneous duplicates)
        intervals = [max(1.0, dt) for dt in intervals]

        if len(intervals) < 2:
            return 0.0

        mu = statistics.mean(intervals)
        sigma = statistics.stdev(intervals)

        if (sigma + mu) == 0:
            return 0.0

        b = (sigma - mu) / (sigma + mu)
        # Map b in [-1, 1] to [0, 1]
        normalized = (b + 1.0) / 2.0
        return max(0.0, min(1.0, normalized))

    def list_user_summaries(self, limit: int = 50) -> list[UserProfileSummary]:
        """Fetch summary profiles for users to power account selector / listings."""
        users = list(self.db.scalars(select(User).order_by(User.created_at.desc()).limit(limit)).all())
        summaries: list[UserProfileSummary] = []

        for user in users:
            tx_count = self.db.scalar(
                select(Transaction.id).where(Transaction.user_id == user.id)
            )
            # Count transactions
            tx_rows = list(
                self.db.scalars(
                    select(Transaction)
                    .where(Transaction.user_id == user.id)
                    .order_by(Transaction.occurred_at.desc())
                    .limit(10)
                ).all()
            )
            total_txs = len(tx_rows)
            latest_tx = tx_rows[0] if tx_rows else None

            if not latest_tx:
                summaries.append(
                    UserProfileSummary(
                        user_id=user.id,
                        email=user.email,
                        display_name=user.display_name,
                        transaction_count=0,
                        last_active=None,
                        composite_deviation_score=0.0,
                        overall_risk_level="LOW",
                        top_risk_indicator="No transaction history",
                    )
                )
                continue

            # Quick evaluation of latest transaction
            profile = self.get_user_behavior_profile(user.id, current_transaction_id=latest_tx.id)
            score = profile.current_deviation.composite_deviation_score if profile.current_deviation else 0.0
            level = profile.current_deviation.overall_risk_level if profile.current_deviation else "LOW"
            top_indicator = profile.risk_indicators[0].title if profile.risk_indicators else "Normal behavior"

            summaries.append(
                UserProfileSummary(
                    user_id=user.id,
                    email=user.email,
                    display_name=user.display_name,
                    transaction_count=profile.behavioral_baseline.historical_transaction_count + 1,
                    last_active=latest_tx.occurred_at,
                    composite_deviation_score=score,
                    overall_risk_level=level,
                    top_risk_indicator=top_indicator,
                )
            )

        return summaries
