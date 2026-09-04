# FraudGuard agent notes

Scaffold only. Do not add fraud scoring, ingest, or UI business logic until that phase is requested.

## Layout

- `backend/` — FastAPI application
- `frontend/` — Next.js UI (`src/pages`, `src/components`, `src/services`, `src/hooks`)
- `ml/` — training data, training scripts, model artifacts, evaluation
- `database/` — SQL migrations and seeds
- `tests/` — cross-cutting unit, integration, and e2e tests (`backend/tests` holds API-local tests)
- `docs/` — architecture and operations notes

## Conventions

- Config and secrets come from environment variables (see `.env.example`).
- No real payment-processor integrations in the MVP.
- Keep scoring explainable (reason codes) when logic is added later.
