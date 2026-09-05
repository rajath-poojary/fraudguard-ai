# FraudGuard

AI-assisted real-time transaction fraud detection and risk intelligence platform.

This repository contains a production-style fraud intelligence platform with a
FastAPI gateway, explainable multi-layer risk engine, PostgreSQL persistence,
offline ML artifacts, and a Next.js analyst dashboard.

## Repository layout

```
fraudguard-ai/
├── backend/                 # FastAPI service
│   ├── app/
│   │   ├── api/             # HTTP / WebSocket route modules
│   │   ├── models/          # ORM / domain persistence models
│   │   ├── schemas/         # Request and response contracts
│   │   ├── services/        # Application use-cases (to be implemented)
│   │   ├── repositories/    # Data access
│   │   ├── core/            # Settings, security, shared utilities
│   │   └── main.py          # Process entrypoint
│   └── tests/               # Backend-local tests
├── frontend/                # Next.js analyst UI
│   └── src/
│       ├── components/      # Reusable UI
│       ├── pages/           # Route-level screens
│       ├── services/        # API client wrappers
│       └── hooks/           # Client hooks (auth, live feed)
├── ml/                      # Offline ML pipeline
│   ├── data/                # Datasets and feature tables
│   ├── training/            # Training jobs
│   ├── models/              # Serialized artifacts (gitignored binaries)
│   └── evaluation/          # Metrics and evaluation reports
├── database/
│   └── migrations/          # Schema migrations
├── tests/                   # Cross-service and e2e tests
├── docs/                    # Project documentation
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## Local setup

1. Copy `.env.example` to `.env` and replace placeholder secrets.
2. Run `docker compose up --build`.
3. API: `http://localhost:8000` · UI: `http://localhost:3000`

The current runtime path is documented in [RUN.md](RUN.md). The architecture
and implementation boundaries are documented in [docs/architecture.md](docs/architecture.md).

## Docs

See [docs/README.md](docs/README.md) for architecture, API, and operations notes.
