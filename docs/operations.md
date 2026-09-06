# Operations Guide

## Quick Start

### Prerequisites

- Docker and Docker Compose (v20.10+)
- Python 3.12+ (for local development)
- PostgreSQL 15+ (or use Docker)
- Redis (or use Docker)

### Local Development Setup

1. **Clone and configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and replace placeholder values with secure secrets
   ```

2. **Start services with Docker Compose**:
   ```bash
   docker compose up --build
   ```

3. **Access the application**:
   - Frontend (UI): http://localhost:3000
   - API (docs): http://localhost:8000/docs
   - Health check: http://localhost:8000/health

### Initialize Database

The database automatically migrates on startup. To manually run migrations:

```bash
# From project root (requires Python and alembic installed)
python -m alembic upgrade head
```

To seed the database with synthetic data for testing:

```bash
python database/seeds/seed_transactions.py --seed 42 --users 25 --merchants 15 --days 30
```

## Production Deployment

### Security Checklist

- [ ] Replace all `change_me` placeholder values in `.env`
- [ ] Use strong JWT_SECRET (32+ random characters)
- [ ] Use strong INGEST_API_KEY (32+ random characters)
- [ ] Set secure database password (unique per environment)
- [ ] Configure ALLOWED_ORIGINS to match your domain
- [ ] Enable HTTPS/TLS in production
- [ ] Set APP_ENV=production
- [ ] Use strong Redis password if exposed
- [ ] Configure automated backups for PostgreSQL

### Environment Variables Reference

| Variable | Purpose | Example | Required |
|----------|---------|---------|----------|
| `APP_ENV` | Environment mode | `production` or `development` | Yes |
| `API_HOST` | Bind address | `0.0.0.0` | Yes |
| `API_PORT` | API port | `8000` | Yes |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend API endpoint | `https://api.example.com` | Yes |
| `ALLOWED_ORIGINS` | CORS allowed domains | `https://app.example.com,https://secure.example.com` | Yes |
| `POSTGRES_HOST` | DB host | `postgres.internal` | Yes |
| `POSTGRES_PORT` | DB port | `5432` | Yes |
| `POSTGRES_DB` | Database name | `fraudguard` | Yes |
| `POSTGRES_USER` | DB user | `fraudguard` | Yes |
| `POSTGRES_PASSWORD` | DB password | (strong secret) | Yes |
| `REDIS_HOST` | Redis host | `redis.internal` | Yes |
| `REDIS_PORT` | Redis port | `6379` | Yes |
| `JWT_SECRET` | Token signing key | (strong random string) | Yes |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` | Yes |
| `JWT_ACCESS_TTL_MINUTES` | Token expiration | `15` | Yes |
| `INGEST_API_KEY` | Ingest endpoint auth | (strong random string) | For simulator |

### Docker Compose Services

- **postgres**: PostgreSQL 15 database (port 5432)
- **redis**: Redis cache (port 6379)
- **api**: FastAPI backend (port 8000, http://api:8000)
- **web**: Next.js frontend (port 3000, http://localhost:3000)

### Database Migrations

All migrations are managed by Alembic. Migrations run automatically on container startup.

To create a new migration:
```bash
python -m alembic revision --autogenerate -m "description of change"
```

To rollback:
```bash
python -m alembic downgrade -1
```

## Monitoring and Diagnostics

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# API documentation
curl http://localhost:8000/docs
```

### Logs

View logs for all services:
```bash
docker compose logs -f
```

View logs for specific service:
```bash
docker compose logs -f api
docker compose logs -f web
docker compose logs -f postgres
```

### Database Access

Connect to PostgreSQL directly:
```bash
docker compose exec postgres psql -U fraudguard -d fraudguard
```

Query transaction statistics:
```sql
SELECT COUNT(*), risk_level, decision FROM transactions GROUP BY risk_level, decision;
SELECT COUNT(*) as fraud_alerts FROM fraud_alerts WHERE status = 'open';
```

## Backup and Recovery

### Backup Database

```bash
docker compose exec postgres pg_dump -U fraudguard fraudguard > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore Database

```bash
docker compose exec -T postgres psql -U fraudguard fraudguard < backup_20240101_120000.sql
```

## Performance Tuning

### PostgreSQL Optimization

Update connection pooling for production:
```sql
-- In postgres configuration
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
```

### Redis Configuration

For high-traffic scenarios:
```
maxmemory 512mb
maxmemory-policy allkeys-lru
```

## Troubleshooting

### API cannot connect to database

1. Verify POSTGRES_HOST and POSTGRES_PORT in .env
2. Check database is running: `docker compose ps`
3. Test connection: `docker compose exec postgres pg_isready`

### Frontend cannot reach API

1. Verify NEXT_PUBLIC_API_BASE_URL points to correct API endpoint
2. Check ALLOWED_ORIGINS in backend includes frontend URL
3. Check API is running: `curl http://localhost:8000/health`

### Database migration fails

1. Check logs: `docker compose logs api`
2. Verify database exists and is accessible
3. Reset and reinitialize: `docker compose down -v && docker compose up --build`

## Maintenance

### Regular Tasks

- Monitor disk space for logs and database
- Review JWT_ACCESS_TTL_MINUTES for security needs
- Audit CORS_ALLOWED_ORIGINS configuration
- Backup database weekly (or use managed database backup)
- Update dependencies monthly: `pip list --outdated`

