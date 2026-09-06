# FraudGuard API Reference

The FraudGuard API provides HTTP endpoints for fraud detection, investigation, and analysis.

## Access

FastAPI generates interactive documentation at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

## Base URL

```
http://localhost:8000/api/v1
```

(Adjust host/port based on deployment; `NEXT_PUBLIC_API_BASE_URL` in `.env` controls the frontend's API endpoint)

## Authentication

All endpoints except auth routes require a bearer token:

```http
Authorization: Bearer <token>
```

Obtain tokens via `/auth/register` or `/auth/login`. Tokens expire after `JWT_ACCESS_TTL_MINUTES` (default: 15).

### Auth Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/auth/register` | Register a new user and return access token |
| `POST` | `/auth/login` | Authenticate with email/password and return access token |

**Request** (Register):
```json
{
  "email": "user@company.com",
  "password": "securepassword",
  "display_name": "John Analyst"
}
```

**Response** (both endpoints):
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer"
}
```

## Transaction Endpoints

### List Transactions

```
GET /transactions?limit=50
```

Returns paginated list of transactions for authenticated user (or all transactions if admin).

**Response**:
```json
{
  "items": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "amount": "150.00",
      "currency": "USD",
      "status": "completed",
      "occurred_at": "2026-01-15T10:30:00Z",
      "analysis": {
        "fraud_probability": 0.042,
        "risk_score": 12.5,
        "risk_level": "LOW",
        "decision": "APPROVE",
        "reasons": ["NORMAL_BEHAVIOR_PROFILE"]
      }
    }
  ],
  "total": 1250
}
```

### Get Transaction Detail

```
GET /transactions/{transaction_id}
```

Returns full transaction record including analysis, metadata, and related entities.

### Create Transaction

```
POST /transactions
```

**Request**:
```json
{
  "user_id": "uuid",
  "merchant_id": "uuid",
  "device_id": "uuid",
  "amount": 150.00,
  "currency": "USD",
  "merchant_category": "electronics",
  "location": "New York, US",
  "ip_address": "198.51.100.1",
  "payment_method": "credit_card"
}
```

Triggers real-time analysis pipeline: validation → feature engineering → model prediction → alert generation.

## Alert Endpoints

### List Fraud Alerts

```
GET /fraud-alerts?limit=50&status=open&severity=high
```

**Query Parameters**:
- `limit` — Number of results (default: 50)
- `status` — Filter by status: `open`, `investigating`, `resolved`
- `severity` — Filter by severity: `low`, `medium`, `high`

**Response**:
```json
{
  "items": [
    {
      "id": "uuid",
      "transaction_id": "uuid",
      "user_id": "uuid",
      "risk_score": "94.5",
      "status": "open",
      "reason_code": "ALERT_ACCOUNT_TAKEOVER",
      "created_at": "2026-01-15T10:35:00Z"
    }
  ],
  "total": 24
}
```

### Get Alert Detail

```
GET /fraud-alerts/{alert_id}
```

## Dashboard & Analytics

### Dashboard Statistics

```
GET /dashboard/statistics
```

Returns real-time metrics: transaction volumes, fraud rates, top risky entities, alerts, and fraud trend.

All metrics are computed dynamically from the database (no hardcoding).

**Response**:
```json
{
  "total_transactions": 2154,
  "total_alerts": 42,
  "high_risk_transactions": 18,
  "blocked_transactions": 12,
  "fraud_rate": 5.6,
  "current_fraud_rate": 5.2,
  "transactions_per_minute": 3.4,
  "financial_exposure": 145000.00,
  "active_investigations": 8,
  "risk_distribution": {
    "LOW": 1980,
    "MEDIUM": 156,
    "HIGH": 18
  },
  "fraud_trend": [
    {
      "date": "2026-01-10",
      "transactions": 220,
      "fraud_count": 8,
      "volume": 44500.00
    }
  ],
  "top_risky_merchants": [...],
  "top_risky_devices": [...],
  "top_risky_users": [...],
  "critical_alerts": [...]
}
```

## Behavioral Intelligence

### List User Profiles

```
GET /behavioral/profiles?limit=50
```

Returns summary of all user behavioral baselines.

### Get User Behavior Profile

```
GET /users/{user_id}/behavior-profile?window_days=90&current_transaction_id={txid}
```

**Response**:
```json
{
  "user_id": "uuid",
  "user_email": "user@example.com",
  "behavioral_baseline": {
    "average_transaction_amount": 125.50,
    "median_transaction_amount": 85.00,
    "average_daily_frequency": 3.2,
    "typical_amount_range": [15.00, 500.00],
    "known_devices": ["device-abc", "device-def"],
    "known_ip_addresses": ["198.51.100.1", "203.0.113.5"],
    "frequent_merchant_categories": [
      { "key": "groceries", "count": 45, "percentage": 35.2 }
    ]
  },
  "current_deviation": {
    "amount_deviation": {
      "value": 1850.00,
      "score": 78,
      "level": "high",
      "explanation": "Amount 18.5× higher than usual ($1,850 vs $100 baseline)"
    },
    "device_novelty": {
      "level": "high",
      "score": 85,
      "explanation": "Device never seen before"
    },
    "overall_risk_level": "HIGH"
  }
}
```

## Network Intelligence

### Get Network Graph

```
GET /network/graph
```

Returns a network of users, devices, merchants, and IPs connected by relationships.

### Get Entity Profile

```
GET /network/entities/{type}/{id}/profile
```

Types: `user`, `device`, `merchant`, `ip`

Returns risk indicators and related transactions for an entity.

### Get Entity Neighborhood

```
GET /network/entities/{type}/{id}/neighborhood?depth=2
```

Returns connected entities (2-hop relationships by default).

### Suspicious Clusters

```
GET /network/clusters/suspicious
```

Returns fraud rings and coordinated fraud clusters detected in the network.

## Temporal Intelligence

### List Temporal Sequences

```
GET /temporal/sequences?pattern=velocity&severity=high&limit=50
```

Returns suspicious temporal patterns (velocity anomalies, impossible travel, etc).

### Get User Temporal Analysis

```
GET /temporal/users/{user_id}/analysis
```

Full timeline analysis with rolling window metrics.

### Get Transaction Temporal Context

```
GET /temporal/transactions/{transaction_id}/context
```

Returns transaction's place in user's sequence, preceding/succeeding events.

## Investigation Cases

### List Cases

```
GET /cases?limit=50&status=open
```

### Get Case Detail

```
GET /cases/{case_id}
```

Full case with timeline, actions, evidence, related transactions.

### Create Case Action

```
POST /cases/{case_id}/actions
```

**Request**:
```json
{
  "action_type": "manual_review_approved|escalate|close|contact_user",
  "note": "Optional investigator note",
  "assigned_to_id": "uuid (optional)"
}
```

Records investigator action and updates case status.

## Admin Endpoints

### Get Admin Profile

```
GET /admin/me
```

Requires `admin` role.

### List Users

```
GET /admin/users
```

### Update User Role

```
PATCH /admin/users/{user_id}/role
```

**Request**:
```json
{
  "role": "ADMIN|INVESTIGATOR|ANALYST"
}
```

### Audit Logs

```
GET /admin/audit-logs?limit=50
```

Returns all system actions (logins, role changes, case actions, etc).

### List Models

```
GET /admin/models
```

### Deploy Model

```
POST /admin/models/{model_id}/deploy
```

### Get Detection Policy

```
GET /admin/policies/{policy_name}
```

### Update Detection Policy

```
PUT /admin/policies/{policy_name}
```

**Request**:
```json
{
  "configuration": {
    "rule_name": "value",
    ...
  }
}
```

## Error Handling

All endpoints return standard error responses:

```json
{
  "detail": "Error description"
}
```

**Status Codes**:

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Created |
| `400` | Invalid request (validation error) |
| `401` | Unauthorized (missing or invalid token) |
| `403` | Forbidden (insufficient permissions) |
| `404` | Not found |
| `409` | Conflict (e.g., duplicate email) |
| `422` | Unprocessable entity (invalid data) |
| `500` | Internal server error |

## Rate Limiting

Not currently implemented. Production deployments should add rate limiting via:
- API gateway (Nginx, Kong)
- Middleware (slowapi, Django REST Throttling)
- Redis-based token bucket

## WebSocket (Future)

Real-time event streaming for:
- Live transaction alerts
- Investigation case updates
- Model deployment progress
- Operational metrics

Endpoint: `ws://localhost:8000/ws/events/{client_id}`

Requires bearer token in query string: `?token={access_token}`

## Examples

### Authenticate and Check Dashboard

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@fraudguard.local","password":"FraudGuard2026!"}'

# Save token
TOKEN="<returned access_token>"

# Check dashboard
curl http://localhost:8000/api/v1/dashboard/statistics \
  -H "Authorization: Bearer $TOKEN"
```

### Create Transaction

```bash
curl -X POST http://localhost:8000/api/v1/transactions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "merchant_id": "...",
    "device_id": "...",
    "amount": 150.00,
    "currency": "USD",
    "location": "New York, US"
  }'
```

### Query Behavioral Profile

```bash
curl "http://localhost:8000/api/v1/users/123e4567-e89b-12d3-a456-426614174000/behavior-profile?window_days=90" \
  -H "Authorization: Bearer $TOKEN"
```

