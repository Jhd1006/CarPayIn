# mock-pg

Mock payment gateway service.

## Responsibilities

- Serve the local card registration WebView
- Complete card registration and issue mock billing keys
- Charge a billing key through `mock-card`
- Notify `carpayin-backend` through configured webhook URLs

## Structure

```text
app/
  api/            FastAPI routes, schemas, and dependencies
  application/    PG card registration and payment use cases
  infra/          Database, repositories, and external clients
migrations/       Alembic migrations
tests/            Unit, API, and integration tests
```

## Runtime

The container starts with:

```text
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```
