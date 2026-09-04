# Database

PostgreSQL schema owned by Alembic-style migrations. No schema SQL has been written yet.

## Layout

| Path | Role |
|------|------|
| `migrations/` | Ordered schema revisions |
| `seeds/` | Demo users, merchants, and sample traffic (later) |

Runtime database files stay on the Compose `postgres_data` volume, not in this folder.
