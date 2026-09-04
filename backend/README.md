# Backend (FastAPI)

HTTP and WebSocket API for FraudGuard. This package is a scaffold: no scoring, ingest, or auth logic yet.

## Layout

| Path | Role |
|------|------|
| `app/main.py` | Process entrypoint |
| `app/api/` | Route modules (`/api/v1`) |
| `app/models/` | SQLAlchemy models |
| `app/schemas/` | Pydantic request/response schemas |
| `app/services/` | Use-cases (rules, scoring, alerts) — empty for now |
| `app/repositories/` | Database access |
| `app/core/` | Settings, security helpers, logging |
| `tests/` | Pytest tests owned by this service |

## Run (later)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
