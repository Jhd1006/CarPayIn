# carpayin-backend

Main Car Pay In API service.

## Responsibilities

- QR login session creation and polling
- Hyundai OAuth callback handling
- Vehicle confirmation
- Card registration order creation and PG webhook handling
- Parking pre-notification and PMS entry webhook handling
- Parking fee lookup, billing-key payment, and PMS payment notification

## Structure

```text
app/
  api/            FastAPI routes, schemas, and dependencies
  application/    Use-case services
  domain/         Domain concepts and errors
  infra/          Database, Redis, security, and external clients
migrations/       Alembic migrations
tests/
  unit/           Use-case and client tests
  api/            HTTP route tests
  integration/    Repository and Redis integration tests
```

## Runtime

The container starts with:

```text
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Required environment variables are defined in the root `docker-compose.yaml`
and `.env.example`.
