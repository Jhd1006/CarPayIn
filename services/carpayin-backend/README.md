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

## Local Development

Install dependencies and run tests from this service directory:

```powershell
pip install -r requirements.txt
python -m pytest tests/unit tests/api -q --import-mode=importlib
```

Run the service outside Docker when local Postgres and Redis are already
available:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Main Endpoints

- `POST /auth/qr-session`
- `GET /auth/hyundai/start`
- `GET /auth/redirect`
- `GET /auth/session/{session_id}/status`
- `POST /auth/confirm-car`
- `POST /auth/refresh`
- `POST /card/order`
- `POST /card/webhook`
- `GET /parking/lots`
- `GET /sim/location`
- `POST /sim/location`
- `POST /parking/navigate`
- `POST /webhook/entry`
- `GET /fee/{session_id}`
- `POST /payment`

The source of truth for request and response contracts is
`../../docs/api/car-pay-in-openapi.yaml`.
