# Car Pay In

Car Pay In is a monorepo for the in-vehicle parking payment flow. It contains
the Android client, the main backend, mock payment/card services, PMS service,
scenario documents, local Docker Compose, and GitLab Registry deployment tools.

## Repository Layout

```text
services/
  android-app/        Android client used for local and in-car testing
  carpayin-backend/   Main API for auth, vehicle, card, parking, and payment
  mock-card/          Mock card company API
  mock-pg/            Mock PG API and card registration WebView
  pms/                Mock parking management system API

docs/
  api/                OpenAPI contract
  DB 스키마/          Database and Redis schema documents
  deployment/         Registry, CI/CD, and deployment notes
  diagrams/           Mermaid sequence diagrams
  use-cases/          Use-case level specifications
  시나리오/           Scenario flow documents

scripts/
  build-push-images.ps1      Local GitLab Registry image build/push helper
  deploy-from-registry.ps1   Pull registry images and run Docker Compose
  start-local-e2e.ps1        Start local E2E dependencies
  stop-local-e2e.ps1         Stop local E2E dependencies
```

## Local Configuration

Copy `.env.example` to `.env` and fill local secrets before running real
Hyundai OAuth.

Required for the main local flow:

```text
PUBLIC_BASE_URL
HYUNDAI_CLIENT_ID
HYUNDAI_CLIENT_SECRET
PG_PUBLIC_BASE_URL
```

Do not commit `.env` or real credentials.

## Local Run

Start the local service stack:

```powershell
docker compose up -d --build
```

Useful ports:

```text
8000  carpayin-backend
8001  pms
8002  mock-pg
8003  mock-card
5432  carpayin-postgres
5433  mock-card-postgres
5434  mock-pg-postgres
5435  pms-postgres
6379  redis
```

## Tests

Run the backend unit/API tests:

```powershell
cd services/carpayin-backend
python -m pytest tests/unit tests/api -q --import-mode=importlib
```

Compile the Android app:

```powershell
cd services/android-app
.\gradlew.bat :app:compileDebugKotlin
```

## CI/CD

Merge requests run a lightweight validation pipeline.

Pushing a semantic version tag builds and pushes runtime images to GitLab
Container Registry:

```powershell
git tag 0.0.2
git push origin 0.0.2
```

Images are pushed as both the semantic version tag and `latest`.

See `docs/deployment/gitlab-registry.md` for registry, local runner, and AWS
pull details.
