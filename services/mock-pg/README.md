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

## Local Development

Install dependencies and run tests from this service directory:

```powershell
pip install -r requirements.txt
python -m pytest tests/unit tests/api -q --import-mode=importlib
```

Run the service outside Docker when its database and mock-card dependency are
available:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
```

## Main Endpoints

- `POST /pg/internal/card-registration/sessions`
- `GET /pg/card-register`
- `POST /pg/card-register`
- `POST /pg/payments/billing`

The API contract is included in `../../docs/api/car-pay-in-openapi.yaml`.
