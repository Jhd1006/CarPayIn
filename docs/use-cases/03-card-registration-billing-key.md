# 03. Card Registration / Billing Key Use Cases

## UC-CARD-001. 카드 등록 order 생성

API:

- `POST /card/order`

입력:

- Bearer app access token
- `plate`
- `bank_name`
- `agree_terms`

출력:

- `order_id`
- PG WebView `pg_url` / `webview_url`

사전 조건:

- app access token이 유효해야 한다.
- 토큰의 `user_id`, `car_id`에 해당하는 차량이 DB에 있어야 한다.
- `agree_terms`가 true여야 한다.
- 차량번호 형식이 유효해야 한다.
- MOLIT 소유자 검증이 통과해야 한다.

처리:

- token에서 `user_id`, `car_id`를 읽는다.
- DB `vehicles`에서 차량 등록 여부를 확인한다.
- 차량번호를 정규화한다.
- MOLIT API로 차량번호와 소유자/차량 매칭을 검증한다.
- `order_id`를 생성한다.
- Redis `mock_pg_card_register:{order_id}`를 pending으로 저장한다.
- PG internal API에 `order_id` 기반 카드 등록 WebView URL 생성을 요청한다.
- `order_id`, `pg_url`, `webview_url`을 반환한다.

Redis 변경:

- `mock_pg_card_register:{order_id}` 저장

DB 변경:

- 필요 시 `vehicles.plate` 업데이트

외부 호출:

- MOLIT owner check
- Mock PG internal card registration session 생성 요청

실패 케이스:

- 인증 실패
- 약관 미동의
- 차량 없음
- 차량번호 형식 오류
- MOLIT 검증 실패
- PG URL 생성 실패

먼저 작성할 테스트:

- 유효한 요청이면 order를 Redis에 저장하고 pg_url/webview_url을 반환한다.
- 약관 미동의면 400을 반환한다.
- MOLIT 검증 실패면 order를 만들지 않는다.
- 차량이 없으면 404를 반환한다.

## UC-CARD-002. 카드 등록 완료 webhook 처리

API:

- `POST /card/webhook`

입력:

- `order_id`
- `billing_key`
- `card_last_four`
- `status`
- PG signature 또는 HMAC

출력:

- `{ "status": "ok" }`

사전 조건:

- webhook signature가 유효해야 한다.
- Redis `mock_pg_card_register:{order_id}`가 pending 상태로 존재해야 한다.
- 연결 대상 차량이 DB에 있어야 한다.

처리:

- HMAC 또는 signature를 검증한다.
- Redis order 상태를 조회한다.
- DB `vehicle_billing_keys`에 billing key를 upsert한다.
- 기존 billing key가 있으면 새 값으로 교체한다.
- Redis order를 삭제하거나 complete 상태로 변경한다.

Redis 변경:

- `mock_pg_card_register:{order_id}` 삭제 또는 complete 처리

DB 변경:

- `vehicle_billing_keys` insert 또는 update

실패 케이스:

- signature 불일치
- order 없음 또는 만료
- webhook status가 active가 아님
- card_last_four 형식 오류
- 차량 없음

먼저 작성할 테스트:

- 정상 webhook이면 vehicle_billing_keys에 active billing key를 저장한다.
- 같은 webhook이 두 번 와도 결과가 깨지지 않는다.
- order가 없으면 400을 반환한다.
- signature가 틀리면 401 또는 400을 반환한다.

