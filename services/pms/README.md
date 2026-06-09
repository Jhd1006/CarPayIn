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

## Local Development

Install dependencies and run tests from this service directory:

```powershell
pip install -r requirements.txt
python -m pytest tests/unit tests/api -q --import-mode=importlib
```

Run the service outside Docker when its database is available:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## Main Endpoints

- `POST /pms/parking/pre-register`
- `POST /pms/lpr/entry`
- `GET /pms/parking/fee`
- `POST /pms/payment/complete`

Short aliases without the `/pms` prefix also exist for local simulation.
The API contract is included in `../../docs/api/car-pay-in-openapi.yaml`.
