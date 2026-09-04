# Database

The PostgreSQL schema is owned by Alembic migrations. SQLite is not supported.

From the repository root, configure `POSTGRES_HOST`, `POSTGRES_PORT`,
`POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` in `.env`, then run:

```bash
\.venv\Scripts\python.exe -m alembic upgrade head
```

## Layout

| Path | Role |
|------|------|
| `migrations/` | Ordered schema revisions |
| `seeds/` | Demo users, merchants, and sample traffic (later) |

Runtime database files stay on the Compose `postgres_data` volume, not in this folder.
