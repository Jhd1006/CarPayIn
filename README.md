# Car Pay-in Cloud Monorepo

클라우드 배포용 Car Pay-in 서비스를 새로 개발하는 monorepo다.

기존 로컬 실험 코드는 `../car-pay-in`에 유지한다.
기능 개발은 `../car-pay-in/docs/use-cases/`의 유스케이스를 기준으로 테스트부터 작성한다.

## 구조

```text
services/
  carpayin-backend/   Car Pay-in main backend
  mockpg/             Mock PG service, 추후 추가
  mockcard/           Mock Card service, 추후 추가
  pms/                Mock Parking PMS service, 추후 추가
packages/
  common/             공유 코드, 추후 필요할 때 추가
```

## 개발 흐름

1. `../car-pay-in/docs/use-cases/`에서 유스케이스를 하나 고른다.
2. 해당 서비스의 `tests/unit/`에 테스트를 먼저 작성한다.
3. `app/application/`에 유스케이스 구현을 추가한다.
4. 필요해지면 `app/api/`, `app/infra/`를 연결한다.

## 첫 개발 대상

- `UC-AUTH-001. QR 로그인 세션 생성`

