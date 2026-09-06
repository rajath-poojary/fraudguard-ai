# Database

The PostgreSQL schema is managed by Alembic migrations. SQLite is not supported for production.

## Quick Start

### Setup

From the repository root, configure these environment variables in `.env`:

- `POSTGRES_HOST` — Database hostname (default: `localhost`)
- `POSTGRES_PORT` — Database port (default: `5432`)
- `POSTGRES_DB` — Database name (default: `fraudguard`)
- `POSTGRES_USER` — Database user (default: `fraudguard`)
- `POSTGRES_PASSWORD` — Database password (must change in production)

Then run migrations:

```bash
# Using Docker Compose (automatic on startup)
docker compose up

# Manual migration with Python
python -m alembic upgrade head
```

## Schema

The database implements a transaction data foundation with 14 core attributes:

| Attribute | Type | Purpose |
|-----------|------|---------|
| `transaction_id` | UUID | Unique transaction identifier |
| `user_id` | UUID | Cardholder/account |
| `merchant_id` | UUID | Merchant entity |
| `device_id` | UUID | Device fingerprint |
| `amount` | Decimal | Transaction amount |
| `currency` | String | Currency code (ISO 4217) |
| `status` | String | Transaction status (completed, blocked, pending, failed) |
| `occurred_at` | Timestamp | Transaction time (UTC) |
| `created_at` | Timestamp | Record creation time (UTC) |
| `merchant_category` | String | MCC or category |
| `ip_address` | String | IP address of transaction origin |
| `location` | String | Geographic location (city, country) |
| `payment_method` | String | Payment instrument type |
| `account_age` | Integer | Days since account creation |

### Self-Referential Chaining

Transactions can reference previous transactions via `previous_transaction_id` to preserve chains:

```sql
SELECT t1.id, t2.id 
FROM transactions t1 
JOIN transactions t2 ON t1.previous_transaction_id = t2.id 
WHERE t1.user_id = $1
ORDER BY t1.occurred_at;
```

### Related Tables

- **Users**: Account entities with authentication
- **Merchants**: Merchant information (category, country)
- **Devices**: Device fingerprints and platforms
- **FraudAlerts**: Fraud detection alerts linked to transactions
- **RiskEvents**: Risk scoring events with reason codes
- **InvestigationCases**: Fraud investigation cases

## Migrations

All migrations are versioned and ordered. To create a new migration:

```bash
python -m alembic revision --autogenerate -m "Add user_risk_flags column"
```

To view migration history:

```bash
python -m alembic history
```

To rollback one version:

```bash
python -m alembic downgrade -1
```

To roll forward to specific version:

```bash
python -m alembic upgrade 0005_investigation_feedback
```

### Migration Reproducibility

- Migrations are **deterministic** — same `seed` produces same schema
- Migrations are **idempotent** — re-running is safe (checks exist before adding)
- Migrations are **ordered** — filename prefixes enforce sequence
- All migrations use **UTC timestamps**

See `migrations/versions/` for all historical changes.

## Seeding

### Synthetic Data Pipeline

Populate the database with realistic transaction chains and fraud scenarios:

```bash
python database/seeds/seed_transactions.py \
  --seed 42 \
  --users 25 \
  --merchants 15 \
  --days 30
```

### Options

- `--seed N` — Random seed for reproducibility (default: 42)
- `--users N` — Number of user profiles (default: 25)
- `--merchants N` — Number of merchants (default: 15)
- `--days N` — Timeline duration in days (default: 30)

### What Gets Created

- Admin user: `admin@fraudguard.local` / `FraudGuard2026!`
- Demo user: `demo@fraudguard.local` / `FraudGuard2026!`
- N merchant profiles with categories, risk levels, and amount ranges
- N user profiles with historical behaviors (amounts, locations, devices)
- Synthetic transaction stream with 8 fraud scenarios:
  - Account takeover
  - Card testing
  - Impossible travel
  - Device compromise
  - Velocity anomaly
  - Coordinated fraud
  - Merchant abuse
  - Exploitation

### Transaction Chains

The seeder generates transactions with `previous_transaction_id` links, creating behavioral chains suitable for temporal analysis and network inference.

## Access Control

All API endpoints use role-based access control:

- **ADMIN**: Full system access
- **INVESTIGATOR**: Case read/write, analytics
- **ANALYST**: Read-only analytics and model performance

Roles are enforced at the API layer via permission decorators.

## Performance

### Indexing Strategy

Key indexes for production queries:

```sql
-- User and transaction lookups
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_occurred_at ON transactions(occurred_at DESC);

-- Risk analysis
CREATE INDEX idx_transactions_risk_level ON transactions(risk_level);
CREATE INDEX idx_fraud_alerts_status ON fraud_alerts(status);

-- Temporal queries
CREATE INDEX idx_transactions_created_at ON transactions(created_at DESC);
```

### Connection Pooling

Production should use connection pooling:

```python
# via SQLAlchemy
create_engine(
  "postgresql://...",
  pool_size=20,
  max_overflow=40,
  pool_pre_ping=True,
)
```

## Backup and Recovery

### Backup

```bash
# Full database dump
pg_dump fraudguard > fraudguard_backup.sql

# Compressed backup
pg_dump fraudguard | gzip > fraudguard_backup.sql.gz
```

### Restore

```bash
# From SQL dump
psql fraudguard < fraudguard_backup.sql

# From compressed backup
gunzip < fraudguard_backup.sql.gz | psql fraudguard
```

### Automated Backups

For production, configure:
- Daily full backups
- Transaction log archiving
- Off-site replication
- Point-in-time recovery testing
