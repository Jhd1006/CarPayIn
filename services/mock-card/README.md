# mock-card

Mock card company API used by the Mock PG service.

## Responsibilities

- Verify card registration input
- Tokenize card data into a mock card token
- Approve billing-key based payment requests

## Structure

```text
app/
  api/            FastAPI routes, schemas, and dependencies
  application/    Card verification and approval use cases
  infra/          Database, repositories, and card security helpers
migrations/       Alembic migrations
k8s/              Kubernetes manifests for the mock-card service
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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8003
```

## Main Endpoints

- `POST /cards/verify`
- `POST /cards/charge`

The API contract is included in `../../docs/api/car-pay-in-openapi.yaml`.
