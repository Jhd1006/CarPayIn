# pms

Mock parking management system API.

## Responsibilities

- Store vehicle pre-registration requests
- Receive simulated LPR entry events
- Calculate parking fees
- Record payment completion notifications

## Structure

```text
app/
  api/            FastAPI routes, schemas, and dependencies
  application/    PMS use-case services
  infra/          Database, repositories, fee calculation, and clients
migrations/       Alembic migrations
tests/            Unit, API, and integration tests
```

## Runtime

The container starts with:

```text
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```
