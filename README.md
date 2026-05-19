# Car Pay-in Cloud Backend

새 클라우드 기반 Car Pay-in backend 구현 공간이다.

기존 로컬 실험 코드는 `../car-pay-in`에 유지하고, 이 폴더에서는 `../car-pay-in/docs/use-cases/` 기준으로 테스트 먼저 작성한 뒤 기능을 구현한다.

## 구조

```text
app/
  api/              HTTP route, request/response schema
  application/      use case service
  domain/           domain model, business rule, error
  infra/            DB, Redis, external client, messaging implementation
  config/           settings, dependency wiring
migrations/         database migration
tests/
  unit/             use case and domain tests
  integration/      repository/client/API integration tests
  e2e/              scenario-level tests
```

## 시작 유스케이스

1. `UC-AUTH-001. QR 로그인 세션 생성`
2. `UC-AUTH-004. 로그인 세션 상태 조회`
3. `UC-AUTH-005. 차량 선택 확정과 앱 토큰 발급`
