# Tests

Cross-cutting tests. Service-local backend tests also live in `backend/tests/`.

## Layout

| Path | Role |
|------|------|
| `unit/` | Pure functions (scoring math, rules, features) once implemented |
| `integration/` | API + database + Redis |
| `e2e/` | Browser flows (login → live feed) |

Runners and CI will be wired when there is code to test.
