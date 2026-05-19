# Use Case Development Guide

## 목적

이 폴더는 5개 시나리오를 기능 구현 가능한 유스케이스 단위로 나눈 문서 모음이다.
새 클라우드 기반 구현에서는 기존 로컬 코드보다 이 문서를 기준으로 테스트와 기능을 작성한다.

## 구현 원칙

- API 계약은 `docs/api/car-pay-in-openapi.yaml`을 우선한다.
- 장기 데이터는 PostgreSQL에 저장한다.
- 짧은 세션성 데이터는 Redis에 TTL 기반으로 저장한다.
- 현대, PMS, PG, 카드사 호출은 client 인터페이스로 분리한다.
- 유스케이스 테스트에서는 외부 서비스를 직접 호출하지 않고 fake client를 사용한다.
- DB repository 테스트는 테스트 DB 또는 transaction rollback 기반으로 검증한다.
- 결제와 webhook은 idempotency를 반드시 테스트한다.

## 권장 개발 순서

1. 공통 기반
   - 설정, clock, id generator, token hash, error type, repository interface, external client interface
2. QR 로그인과 현대 OAuth
   - 세션 생성, OAuth 시작, callback 처리, polling
3. 차량 확정과 앱 토큰
   - 차량 목록 검증, 차량 등록, app token 발급
4. 카드 등록
   - card order 생성, PG webhook 처리, billing key 저장
5. 입차
   - pre-notify, PMS 사전 등록, entry webhook, parking session 생성
6. 요금 조회와 결제
   - fee quote, payment pending, PG 승인, PMS paid notify
7. Mock 서비스
   - PMS, Mock PG, Mock Card 구현과 통합 테스트

## 테스트 계층

- Use case unit test: 핵심 비즈니스 규칙을 fake repository/client로 검증한다.
- API test: request/response, status code, auth guard를 검증한다.
- Repository test: 실제 테스트 DB에 저장/조회되는지 검증한다.
- Integration/E2E test: 주요 성공 흐름만 최소 개수로 검증한다.

## 문서 파일

- `01-auth-qr-oauth.md`
- `02-vehicle-confirmation.md`
- `03-card-registration-billing-key.md`
- `04-entry-parking-session.md`
- `05-fee-payment-exit.md`
- `06-mock-services.md`

