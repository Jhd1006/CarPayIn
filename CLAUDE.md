# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Run all Python service tests
```powershell
make test
```

### Run tests for a single service
```powershell
cd services/carpayin-backend
python -m pytest tests/unit tests/api -q --import-mode=importlib

# Other services follow the same pattern:
cd services/mock-card && python -m pytest tests/unit tests/api -q --import-mode=importlib
cd services/mock-pg   && python -m pytest tests/unit tests/api -q --import-mode=importlib
cd services/pms       && python -m pytest tests/unit tests/api -q --import-mode=importlib
```

### Run a single test file
```powershell
cd services/carpayin-backend
python -m pytest tests/unit/auth/test_uc_auth_001_create_qr_session.py -q --import-mode=importlib
```

### Start the full local stack
```powershell
docker compose up -d --build
```

### Compile the Android app
```powershell
cd services/android-app
.\gradlew.bat :app:compileDebugKotlin
```

### Database migrations (per service)
```powershell
cd services/carpayin-backend
alembic upgrade head
```

## Architecture

### Monorepo structure

Four independent Python FastAPI services under `services/`, each with the same internal layout:

```
app/
  main.py          # FastAPI app, lifespan, exception handlers
  api/
    deps.py        # All dependency injection wired here (singletons at module load)
    routes/        # Thin HTTP handlers, delegate to application services
    schemas/       # Pydantic request/response models
  application/     # Use-case services (Command → execute() → Result)
  domain/          # Domain models and repository interfaces
  infra/
    clients/       # Outbound HTTP adapters (Hyundai OAuth, PG, PMS, MOLIT)
    db/            # SQLAlchemy session factory
    messaging/     # (carpayin-backend) MQTT/SQS notification publishers
    redis/         # Redis store wrappers for transient state
    repositories/  # SQLAlchemy implementations of domain repositories
    workers/       # Background threads (outbox poller, retry worker)
```

### Layered dependency rule

Routes → Application services → Domain interfaces. Infra implementations are injected in `app/api/deps.py`, which is the single wiring point. Application services never import from `infra/` directly; they receive interfaces via constructor injection.

### carpayin-backend: core payment flow

The main service handles the end-to-end in-vehicle parking payment:

1. **Auth** – QR-based Hyundai OAuth login → temp token → vehicle confirm → app JWT + refresh token
2. **Card** – MOLIT plate verification → PG card registration order → billing key stored via webhook
3. **Parking** – Pre-notify registers vehicle intent; PMS entry webhook creates a `ParkingSession`
4. **Payment** – Fee quote from PMS cached in Redis → charge via PG → PMS notified → MQTT/SQS notification to car

Background workers:
- `NotifyRetryWorker` – retries failed MQTT/SQS entry and payment notifications stored in Redis
- `PaymentOutboxWorker` – polls a DB outbox table to reliably deliver payment events

### Notification publisher selection

`build_notification_publisher()` in `app/infra/support.py` selects at startup:
- **SQS** if `SQS_NOTIFICATION_QUEUE_URL` is set (AWS/staging/prod)
- **MQTT** as fallback (local dev, broker on port 1883)

### Mock services

`mock-pg` and `mock-card` simulate the real payment gateway and card company. `pms` simulates the parking management system. All three are real FastAPI services with their own Postgres and Alembic migrations. `mock-pg` calls `mock-card` internally to verify cards and posts webhooks back to `carpayin-backend`.

### Environment and local config

Before running the stack, copy `.env.example` to `.env`. `PUBLIC_BASE_URL`, `HYUNDAI_CLIENT_ID`, and `HYUNDAI_CLIENT_SECRET` are required; the rest default to local mock values. `deps.py` enforces non-default values for `PUBLIC_BASE_URL` and Hyundai credentials at startup (raises `RuntimeError` if missing or placeholder).

For Android: copy `services/android-app/local.properties.example` to `local.properties`.

## Testing conventions

Test files are named `test_uc_{domain}_{number}_{use_case_name}.py`. The use-case number maps to `docs/use-cases/`.

### Test layers

| Layer | Location | What it tests | Dependencies |
|---|---|---|---|
| Unit | `tests/unit/` | Application service business rules | Fake classes (in-memory dicts), no DB/Redis/HTTP |
| API | `tests/api/` | HTTP contract: status codes, request parsing, auth guard | `TestClient` + `app.dependency_overrides` with Stub services |
| Integration | `tests/integration/` | Real DB/Redis/repository wiring | Actual infra |
| E2E | `tests/e2e/` | Full user flows (minimal) | Full stack |

### Unit test pattern

```python
command = SomeCommand(...)
result = service.execute(command)
assert result.field == expected
# also assert Fake side-effects (saved_sessions, published_calls, etc.)
```

Use `Fake{Role}` classes that store state in dicts/lists. One test function = one behavior or one failure condition.

### API test pattern

Use `app.dependency_overrides` to swap real services for `Stub{Service}` classes. Always back up and restore overrides (never call `dependency_overrides.clear()`):

```python
original = app.dependency_overrides.copy()
app.dependency_overrides[get_some_service] = lambda: StubSomeService()
try:
    with TestClient(app) as client:
        yield client
finally:
    app.dependency_overrides = original
```

Webhook endpoints use `X-Webhook-Timestamp` / `X-Webhook-Signature` headers instead of Bearer tokens.

### Status code mapping

- `422` – Pydantic request parsing failure
- `400` – `ValueError` from application service (mapped in `main.py` exception handlers)
- `401` – missing/invalid token, or auth-related `ValueError` message
- `502` – `RuntimeError` (downstream service failure)

## Key reference docs

- API contract: `docs/api/car-pay-in-openapi.yaml`
- Use-case specs: `docs/use-cases/`
- Sequence diagrams: `docs/diagrams/` (Mermaid `.mmd` files)
- DB/Redis schemas: `docs/DB schemas/`
- Test conventions: `docs/conventions/unit-testing-conventions.md`, `docs/conventions/api-testing-conventions.md`
