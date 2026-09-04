# FraudGuard API

FastAPI generates the interactive OpenAPI documentation at `/docs` and the
OpenAPI schema at `/openapi.json`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Register a user and return a bearer token |
| POST | `/auth/login` | Authenticate and return a bearer token |
| POST | `/transactions` | Persist and analyze a transaction |
| GET | `/transactions` | List the authenticated user's transactions |
| GET | `/transactions/{id}` | Retrieve one transaction and its analysis |
| POST | `/transactions/simulate` | Run the transaction processing flow |
| GET | `/fraud-alerts` | List the authenticated user's alerts |
| GET | `/fraud-alerts/{id}` | Retrieve one fraud alert |
| GET | `/dashboard/statistics` | Return authenticated-user risk totals |

Transaction creation and simulation run validation, persistence, feature
generation, supervised prediction, Isolation Forest scoring, risk scoring, and
result persistence before returning fraud probability, anomaly score, risk
score, level, decision, and reasons.

Authentication uses a one-way password hash and short-lived JWT bearer tokens.
New accounts receive the `user` role. The `admin` role is persisted in
PostgreSQL, included in tokens, and enforced against the current database user
for admin-only routes such as `/admin/me`.
# API

Version prefix: `/api/v1`.

Endpoints (auth, transactions, alerts, cases, stats, WebSocket) will be listed here when routers are implemented.
