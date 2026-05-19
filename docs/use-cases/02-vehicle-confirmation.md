# 02. Vehicle Confirmation Use Cases

## UC-AUTH-005. 차량 선택 확정과 앱 토큰 발급

API:

- `POST /auth/confirm-car`

입력:

- Bearer 임시 access token
- `car_id`
- `vin_hash`

출력:

- app access token
- app refresh token
- user 정보
- 선택된 car 정보

사전 조건:

- 차량 확정용 임시 access token이 유효해야 한다.
- Redis `hyundai_oauth:{session_id}` 또는 `app_login_result:{session_id}`에 차량 목록이 있어야 한다.
- 요청 `car_id`가 현대에서 받은 차량 목록에 포함되어야 한다.
- 요청 `vin_hash`가 QR 세션의 `vin_hash`와 일치해야 한다.

처리:

- 차량 확정용 임시 token에서 `user_id`, `session_id`를 확인한다.
- 차량 목록에 `car_id`가 있는지 검증한다.
- QR 세션의 `vin_hash`와 요청값을 비교한다.
- DB `vehicles`에 차량을 upsert한다.
- 최종 app access token과 refresh token을 발급한다.
- refresh token 원문은 저장하지 않고 hash만 `app_refresh_tokens`에 저장한다.
- Redis `app_login_result:{session_id}`는 사용 완료 상태로 갱신하거나 TTL 만료에 맡긴다.

Redis 변경:

- 필요 시 `app_login_result:{session_id}` 사용 완료 처리

DB 변경:

- `vehicles` upsert
- `app_refresh_tokens` insert

실패 케이스:

- 임시 token 만료
- `car_id`가 차량 목록에 없음
- `vin_hash` 불일치
- QR 세션 만료

먼저 작성할 테스트:

- 유효한 car_id와 vin_hash면 차량을 저장하고 app token을 발급한다.
- refresh token 원문은 DB에 저장하지 않는다.
- 차량 목록에 없는 car_id면 400을 반환한다.
- vin_hash가 다르면 400을 반환한다.

## UC-AUTH-006. 앱 access token 재발급

API:

- `POST /auth/refresh`

입력:

- app refresh token

출력:

- 새 app access token
- 필요한 경우 새 app refresh token

사전 조건:

- refresh token hash가 `app_refresh_tokens`에 active 상태로 존재해야 한다.
- 만료되지 않아야 한다.

처리:

- refresh token hash를 계산한다.
- DB에서 active token을 조회한다.
- 만료된 token이면 expired 상태로 변경한다.
- 유효하면 새 access token을 발급한다.

DB 변경:

- 필요 시 `app_refresh_tokens.status` 업데이트

실패 케이스:

- token 없음
- revoked
- expired

먼저 작성할 테스트:

- active refresh token이면 새 access token을 반환한다.
- 만료된 token이면 401을 반환하고 expired로 표시한다.
- 원문 refresh token은 저장하지 않는다.

