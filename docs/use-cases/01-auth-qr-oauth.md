# 01. QR Login / Hyundai OAuth Use Cases

## UC-AUTH-001. QR 로그인 세션 생성

API:

- `POST /auth/qr-session`

입력:

- `login_session_id`
- `vin_hash`

출력:

- QR 코드로 표시할 `login_url`

사전 조건:

- `login_session_id`가 비어 있지 않아야 한다.
- `vin_hash`가 비어 있지 않아야 한다.

처리:

- Redis `qr_session:{login_session_id}`를 생성한다.
- 상태는 `pending`으로 저장한다.
- TTL은 15분으로 설정한다.
- 로그인 URL은 `/auth/hyundai/start?session_id={login_session_id}` 형식으로 만든다.

Redis 변경:

- `qr_session:{session_id}` 저장

DB 변경:

- 없음

실패 케이스:

- `login_session_id` 누락
- `vin_hash` 누락
- 이미 완료된 세션 재사용

먼저 작성할 테스트:

- 정상 요청이면 Redis에 pending QR 세션을 저장한다.
- 응답 `login_url`에 session_id가 포함된다.
- 필수값이 없으면 400을 반환한다.

## UC-AUTH-002. 현대 OAuth 로그인 시작

API:

- `GET /auth/hyundai/start?session_id={session_id}`

입력:

- `session_id`

출력:

- 현대 OAuth authorize URL로 302 redirect

사전 조건:

- Redis에 `qr_session:{session_id}`가 있고 상태가 `pending`이어야 한다.

처리:

- `oauth_state` 난수를 생성한다.
- Redis `oauth_state:{oauth_state}`에 `session_id` 매핑을 저장한다.
- 현대 OAuth URL을 생성한다.
- OAuth `state`에는 `session_id`가 아니라 `oauth_state`를 넣는다.

Redis 변경:

- `oauth_state:{oauth_state}` 저장

DB 변경:

- 없음

외부 호출:

- 없음. 브라우저 redirect만 수행한다.

실패 케이스:

- QR 세션 없음
- QR 세션 만료
- QR 세션이 pending이 아님

먼저 작성할 테스트:

- pending QR 세션이면 oauth_state를 저장하고 302를 반환한다.
- redirect URL에 client_id, redirect_uri, state가 포함된다.
- 만료된 세션이면 400을 반환한다.

## UC-AUTH-003. 현대 OAuth callback 처리

API:

- `GET /auth/redirect`

입력:

- `code`
- `state`

출력:

- callback 처리 완료 화면 또는 polling 안내 응답

사전 조건:

- Redis `oauth_state:{state}`가 존재해야 한다.
- 매핑된 `qr_session:{session_id}`가 존재해야 한다.

처리:

- `oauth_state`로 원래 `session_id`를 찾는다.
- 현대 OAuth token API에 code를 보내 access/refresh token을 받는다.
- 현대 user profile API로 `user_id`, `name`을 조회한다.
- 현대 vehicle list API로 차량 목록을 조회한다.
- DB `users`를 upsert한다.
- 현대 refresh token을 암호화해서 `hyundai_tokens`에 저장한다.
- 현대 access token은 Redis `hyundai_access:{user_id}`에만 캐시한다.
- Redis `hyundai_oauth:{session_id}`에 OAuth 임시 결과를 저장한다.
- Redis `app_login_result:{session_id}`에 polling 결과를 저장한다.
- `oauth_state`는 used 또는 삭제 상태로 바꾼다.

Redis 변경:

- `hyundai_access:{user_id}` 저장
- `hyundai_oauth:{session_id}` 저장
- `app_login_result:{session_id}` 저장
- `oauth_state:{state}` used 처리 또는 삭제

DB 변경:

- `users` upsert
- `hyundai_tokens` upsert

외부 호출:

- Hyundai token API
- Hyundai user profile API
- Hyundai vehicle list API

실패 케이스:

- `state` 없음 또는 만료
- `code` 없음
- 현대 token API 실패
- 사용자 정보 조회 실패
- 차량 목록 조회 실패

먼저 작성할 테스트:

- 정상 callback이면 user와 hyundai token을 저장한다.
- 현대 access token은 DB가 아니라 Redis에만 저장한다.
- 차량 목록을 app_login_result에 저장한다.
- 잘못된 state면 400을 반환한다.
- 현대 API 실패면 QR 세션을 failed로 표시한다.

## UC-AUTH-004. 로그인 세션 상태 조회

API:

- `GET /auth/session/{session_id}/status`

입력:

- `session_id`

출력:

- `pending`
- `complete`
- 완료 시 사용자 정보, 차량 목록, 차량 확정용 임시 token

사전 조건:

- QR 세션 또는 app login result가 Redis에 있어야 한다.

처리:

- Redis `app_login_result:{session_id}`를 먼저 조회한다.
- 없으면 `qr_session:{session_id}` 상태를 조회한다.
- 완료 전이면 `pending`을 반환한다.
- 완료 후면 사용자 정보와 차량 목록을 반환한다.

Redis 변경:

- 없음

DB 변경:

- 없음

실패 케이스:

- 세션 없음
- 세션 만료
- OAuth 실패 상태

먼저 작성할 테스트:

- OAuth 완료 전이면 pending을 반환한다.
- app_login_result가 있으면 complete와 차량 목록을 반환한다.
- 세션이 없으면 404를 반환한다.

