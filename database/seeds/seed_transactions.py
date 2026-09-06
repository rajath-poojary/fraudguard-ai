"""Database Seeder for Historical Transactions, Behavioral Profiles, and Fraud Alerts.

Populates PostgreSQL with realistic users, devices, merchants, IP relationships,
and historical transaction chains created by the synthetic data pipeline.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import sys
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

# Allow execution both as a module and standalone script
from pathlib import Path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
backend_path = repo_root / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.entities import Device, FraudAlert, Merchant, RiskEvent, Transaction, User
from ml.data.pipeline import SyntheticTransactionGenerator


def seed_database(
    db: Session,
    seed: int = 42,
    num_users: int = 25,
    num_merchants: int = 15,
    duration_days: int = 30,
    admin_email: str = "admin@fraudguard.local",
    demo_email: str = "demo@fraudguard.local",
    default_password: str = "FraudGuard2026!",
) -> dict[str, int]:
    """Run synthetic generator and persist world entities and historical transactions to database."""
    print(f"Initializing Synthetic Generator (seed={seed}, duration={duration_days} days)...")
    generator = SyntheticTransactionGenerator(
        seed=seed,
        duration_days=duration_days,
    )
    generator.initialize_world(num_users=num_users, num_merchants=num_merchants)

    # Ensure admin user exists
    admin_user = db.scalar(select(User).where(User.email == admin_email))
    if not admin_user:
        admin_user = User(
            email=admin_email,
            password_hash=hash_password(default_password),
            display_name="Security Admin",
            role="admin",
            is_active=True,
        )
        db.add(admin_user)
        db.flush()

    # Ensure demo user exists
    demo_user = db.scalar(select(User).where(User.email == demo_email))
    if not demo_user:
        demo_user = User(
            email=demo_email,
            password_hash=hash_password(default_password),
            display_name="Demo Analyst",
            role="user",
            is_active=True,
        )
        db.add(demo_user)
        db.flush()

    # Create merchants in DB
    merchant_map: dict[UUID, Merchant] = {}
    for m_prof in generator.merchants:
        existing_m = db.scalar(select(Merchant).where(Merchant.external_id == m_prof.external_id))
        if not existing_m:
            db_merchant = Merchant(
                id=m_prof.merchant_id,
                external_id=m_prof.external_id,
                name=m_prof.name,
                category=m_prof.category,
                country_code=m_prof.country_code,
            )
            db.add(db_merchant)
            merchant_map[m_prof.merchant_id] = db_merchant
        else:
            merchant_map[m_prof.merchant_id] = existing_m
    db.flush()

    # Create users & devices in DB
    user_map: dict[UUID, User] = {}
    for u_prof in generator.users:
        existing_u = db.scalar(select(User).where(User.email == u_prof.email))
        if not existing_u:
            db_user = User(
                id=u_prof.user_id,
                email=u_prof.email,
                password_hash=hash_password(default_password),
                display_name=u_prof.display_name,
                role="user",
                is_active=True,
            )
            db.add(db_user)
            user_map[u_prof.user_id] = db_user
            db.flush()

            for dev in u_prof.devices:
                db_device = Device(
                    id=dev.device_id,
                    user_id=db_user.id,
                    fingerprint=dev.fingerprint,
                    platform=dev.platform,
                )
                db.add(db_device)
        else:
            user_map[u_prof.user_id] = existing_u
    db.flush()

    # Generate complete transaction stream with all 8 fraud scenarios
    raw_txs = generator.generate_complete_dataset(
        num_users=len(generator.users),
        num_merchants=len(generator.merchants),
    )

    # Insert transactions, preserving previous_transaction_id foreign keys in topological/chronological order
    tx_inserted = 0
    alerts_inserted = 0
    events_inserted = 0

    for tx in raw_txs:
        # Check if transaction already exists
        existing_tx = db.get(Transaction, tx.transaction_id)
        if existing_tx:
            continue

        # Score calculations for the historical record
        if tx.is_fraud:
            risk_score = Decimal(str(round(generator.rng.uniform(78.0, 98.0), 2)))
            risk_level = "HIGH"
            decision = "BLOCK"
            fraud_prob = Decimal("0.9200")
            anomaly = Decimal("0.85000")
            reasons = [f"RULE_FRAUD_{tx.fraud_scenario.upper()}" if tx.fraud_scenario else "HIGH_RISK_ANOMALY"]
        else:
            risk_score = Decimal(str(round(generator.rng.uniform(2.0, 24.0), 2)))
            risk_level = "LOW"
            decision = "APPROVE"
            fraud_prob = Decimal("0.0400")
            anomaly = Decimal("0.08000")
            reasons = ["NORMAL_BEHAVIOR_PROFILE"]

        # Validate previous_transaction_id exists in database if set
        prev_id = tx.previous_transaction_id
        if prev_id and not db.get(Transaction, prev_id):
            prev_id = None

        db_tx = Transaction(
            id=tx.transaction_id,
            user_id=tx.user_id,
            merchant_id=tx.merchant_id,
            device_id=tx.device_id,
            amount=tx.amount,
            currency=tx.currency,
            status="blocked" if tx.is_fraud else tx.transaction_status,
            occurred_at=tx.timestamp,
            merchant_category=tx.merchant_category,
            ip_address=tx.ip_address,
            location=tx.location,
            account_age=tx.account_age,
            payment_method=tx.payment_method,
            previous_transaction_id=prev_id,
            is_fraud=tx.is_fraud,
            fraud_scenario=tx.fraud_scenario,
            fraud_probability=fraud_prob,
            anomaly_score=anomaly,
            risk_score=risk_score,
            risk_level=risk_level,
            decision=decision,
            reasons=reasons,
            metadata_json={
                **tx.metadata,
                "location": tx.location,
                "ip_address": tx.ip_address,
                "payment_method": tx.payment_method,
                "account_age": tx.account_age,
            },
        )
        db.add(db_tx)
        db.flush()
        tx_inserted += 1

        # If fraudulent, create FraudAlert & RiskEvent
        if tx.is_fraud:
            reason_code = f"ALERT_{tx.fraud_scenario.upper()}" if tx.fraud_scenario else "RISK_ALERT"
            db_alert = FraudAlert(
                id=uuid4(),
                transaction_id=db_tx.id,
                user_id=tx.user_id,
                risk_score=risk_score,
                status="open",
                reason_code=reason_code,
            )
            db.add(db_alert)
            alerts_inserted += 1

            db_event = RiskEvent(
                id=uuid4(),
                transaction_id=db_tx.id,
                user_id=tx.user_id,
                event_type="fraud_detection",
                reason_code=reason_code,
                risk_score=risk_score,
                details={
                    "scenario": tx.fraud_scenario,
                    "metadata": tx.metadata,
                    "location": tx.location,
                },
            )
            db.add(db_event)
            events_inserted += 1

    db.commit()

    return {
        "merchants": len(merchant_map),
        "users": len(user_map),
        "transactions": tx_inserted,
        "fraud_alerts": alerts_inserted,
        "risk_events": events_inserted,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed database with synthetic fraud foundation data.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--users", type=int, default=25, help="Number of user profiles")
    parser.add_argument("--merchants", type=int, default=15, help="Number of merchant entities")
    parser.add_argument("--days", type=int, default=30, help="Timeline duration in days")
    args = parser.parse_args()

    with SessionLocal() as db:
        stats = seed_database(
            db,
            seed=args.seed,
            num_users=args.users,
            num_merchants=args.merchants,
            duration_days=args.days,
        )
        print("\n--- Seeding Completed Successfully ---")
        for k, v in stats.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
