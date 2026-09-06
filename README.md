# FraudGuard X

AI-assisted real-time transaction fraud detection and risk intelligence platform.

**FraudGuard X** is a production-grade fraud intelligence system that combines explainable ML with behavioral analysis to detect and investigate fraudulent transactions. It features:

- **Real-time Detection**: Multi-layer risk engine combining supervised ML, anomaly detection, behavioral profiling, and rule-based signals
- **Explainability**: Feature attribution, reason codes, and signal evidence for every decision
- **Investigation**: Case management system with timeline reconstruction and network analysis
- **Temporal Intelligence**: Transaction chaining and behavioral baseline deviation analysis
- **Network Analysis**: Graph-based fraud ring detection across devices, merchants, and IPs
- **Customizable Risk Engine**: Rule editor and model configuration without redeployment
- **Production Ready**: PostgreSQL persistence, audit logging, role-based access control

## System Overview

FraudGuard X implements an event-centric, entity-aware platform:

```
Transaction → Normalization → Historical Context → Feature Engineering
                                                           ↓
                    ┌─────────────────────────────────────┼──────────────────┐
                    ↓                                      ↓                  ↓
            Behavioral Profiling            Device Intelligence      Network Analysis
                    ↓                                      ↓                  ↓
                                     ML Fusion Engine
                                            ↓
                                  Probability Calibration
                                            ↓
                                     Decision Engine
                                            ↓
                        ┌────────────────────┼──────────────────┐
                        ↓                    ↓                  ↓
                    Alerts          Investigation Cases    Analytics
```

**Key Principle**: The final fraud probability must come from a trained and calibrated model. The platform does not use manually weighted averages of arbitrary signals.

## Quick Start

### Prerequisites

- Docker & Docker Compose (v20.10+)
- Python 3.12+ (for local development)
- 2GB free disk space
- Ports 3000 (UI), 8000 (API), 5432 (DB), 6379 (Redis) available

### Run Locally

1. **Clone and configure**:
   ```bash
   git clone https://github.com/your-org/fraudguard-ai.git
   cd fraudguard-ai
   cp .env.example .env
   # Edit .env with your secrets (see .env.example for guidance)
   ```

2. **Start services**:
   ```bash
   docker compose up --build
   ```

3. **Access the system**:
   - **UI**: http://localhost:3000 (login with demo@fraudguard.local / FraudGuard2026!)
   - **API docs**: http://localhost:8000/docs
   - **Health check**: http://localhost:8000/health

4. **Seed sample data** (optional):
   ```bash
   docker compose exec api python database/seeds/seed_transactions.py \
     --seed 42 --users 25 --merchants 15 --days 30
   ```

## Architecture

### Backend (FastAPI)

- **api/v1/**: HTTP endpoints organized by domain
  - `auth.py` — User registration, login, token management
  - `dashboard.py` — Analytics and operational metrics
  - `transactions.py` — Transaction ingestion and stream
  - `prediction.py` — Real-time fraud scoring
  - `behavior.py` — Behavioral profiling and deviation analysis
  - `temporal.py` — Transaction chaining and velocity analysis
  - `network.py` — Device/merchant/IP graph analysis
  - `investigations.py` — Case management and timeline
  - `admin.py` — System configuration and user management

- **models/**: SQLAlchemy ORM entities (Transaction, User, Device, Merchant, etc.)

- **services/**: Domain logic (behavior_engine, risk_engine, network_intelligence, etc.)

- **core/**: Cross-cutting concerns (config, security, audit, database)

### Frontend (Next.js + React)

- **pages/**: Route-level components
  - `dashboard.tsx` — Command center with real-time metrics
  - `transactions/` — Transaction stream inspection
  - `behavioral.tsx` — User behavioral profiles
  - `network.tsx` — Entity network graphs
  - `investigations.tsx` — Fraud case management
  - `admin.tsx` — System configuration

- **services/api.ts** — API client with type-safe contracts

- **hooks/useAuth.ts** — Token-based authentication

- **components/**: Reusable UI elements (loading states, error boundaries, risk badges)

### Database (PostgreSQL)

14-column transaction foundation with self-referential chaining:

```sql
Transactions:
  id, user_id, merchant_id, device_id,
  amount, currency, status,
  occurred_at, created_at,
  merchant_category, ip_address, location, payment_method, account_age,
  previous_transaction_id (self-reference)

Supporting:
  Users, Merchants, Devices, FraudAlerts, RiskEvents, InvestigationCases
```

See [database/README.md](database/README.md) for full schema and migrations.

### ML Pipeline

Located in `ml/`:

- **data/**: Synthetic transaction generator with 8 fraud scenarios
- **training/**: Model training scripts (supervised, anomaly detection)
- **models/**: Serialized artifacts (fraud_model.joblib, preprocessor, metrics)
- **evaluation/**: Performance reports and ablation studies

## Key Features

### Real-Time Detection

Every transaction is scored by:

1. **Supervised Fraud Model** — Calibrated RF/GB classifier
2. **Anomaly Detection** — Isolation Forest for distribution shifts
3. **Behavioral Deviation** — Amount, frequency, location, device changes
4. **Velocity Signals** — Burst detection, rapid-fire transactions
5. **Network Intelligence** — Device/IP/merchant associations
6. **Rule Engine** — Hard stops (e.g., impossible travel)

Scores are fused via a secondary calibration model, producing a final probability (0-1) and decision (APPROVE/REVIEW/BLOCK/CHALLENGE/HOLD).

### Explainability

Every decision includes:

- **Reason codes**: Machine-readable signal categories
- **Feature attribution**: SHAP values showing contribution of key features
- **Evidence**: Supporting facts (velocity spike, location mismatch, etc.)
- **Baseline comparison**: How this transaction deviates from history

### Investigation Workflow

Analysts can:

- Open cases linked to alerts
- Review transaction chains (previous_transaction_id navigation)
- Inspect device/merchant/IP networks
- Add manual notes and adjudicate
- Track timeline of related events
- Provide feedback for model retraining

### Configurable Risk Engine

Non-technical operators can:

- Edit fraud rules without deployment
- Adjust decision thresholds per business rule
- A/B test new signals
- Enable/disable detection models
- Configure retry/challenge policies

## Deployment

### Docker Compose (Development)

```bash
docker compose up --build
```

Services: `postgres`, `redis`, `api`, `web`

### Production Deployment

See [docs/operations.md](docs/operations.md) for:

- Security checklist
- Environment configuration
- Database backup/recovery
- Performance tuning
- Monitoring and troubleshooting

## API Reference

Full OpenAPI documentation available at `http://localhost:8000/docs` when running.

### Example: Check Transaction

```bash
curl -X POST http://localhost:8000/api/v1/prediction/predict \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "amount": 150.00,
    "currency": "USD",
    "merchant_id": "...",
    "device_id": "...",
    "location": "New York, US"
  }'
```

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/architecture.md](docs/architecture.md) | System design and flow |
| [docs/api.md](docs/api.md) | HTTP endpoint contracts |
| [docs/operations.md](docs/operations.md) | Deployment, monitoring, troubleshooting |
| [database/README.md](database/README.md) | Schema, migrations, seeding |

## Development

### Running Tests

```bash
# Backend tests
cd backend
pytest tests/

# E2E tests
pytest tests/e2e/
```

### Code Quality

```bash
# Type checking (Python)
mypy backend/

# Linting (Python)
pylint backend/

# Format (Python)
black backend/
```

## Security

- OAuth 2.0 Bearer tokens for authentication
- Role-based access control (ADMIN, INVESTIGATOR, ANALYST)
- Audit logging of all actions
- JWT expiration (default: 15 minutes)
- Secrets management via environment variables
- CORS configured for specific origins

For security considerations, see [docs/operations.md](docs/operations.md#security-checklist).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

See [LICENSE](LICENSE).

## Support

- **Issues**: GitHub Issues for bug reports
- **Questions**: Discussions forum
- **Incidents**: [ops@example.com](mailto:ops@example.com)

