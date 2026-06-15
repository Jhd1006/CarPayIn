# 05. Fee / Payment / Exit Use Cases

## 알림 실패 재시도

결제 성공과 알림 발송은 분리한다. 알림 실패가 결제 롤백을 유발하지 않는다.

처리 흐름:

- PG 결제가 성공하면 `transactions`를 `success`로 갱신한다.
- MQTT로 앱에 결제 완료 알림을 발송한다.
- PMS에 `POST /payment/complete`로 결제 완료를 통보한다.
- PMS 통보가 실패하면 `pms_payment_retry:{tx_id}` Redis 키로 저장한다 (TTL 7일).
- `NotifyRetryWorker`가 60초마다 실패 키를 순회해 PMS 통보를 재시도한다.
- 재시도 성공 시 해당 키를 삭제한다.

이 구조를 쓰는 이유:

- 결제 성공 자체는 `transactions`에 보존되고, PMS 통보 실패는 별도로 재시도한다.
- PMS 통보가 실패하면 출구 차단기가 열리지 않으므로 빠른 재시도가 필요하다.
- Redis TTL을 쓰는 이유: 재시도 이벤트는 단기 용도이고, 성공 후에는 자동 삭제된다.

## UC-PAY-001. 현재 주차 요금 조회와 quote 생성

API:

- `GET /fee/{session_id}`

입력:

- Bearer app access token
- `session_id`

출력:

- `session_id`
- `lot_id`
- `amount`
- `currency`
- `entry_time`
- `status=active`

사전 조건:

- app access token이 유효해야 한다.
- `parking_sessions`에 active session이 있어야 한다.
- session의 `car_id`와 token의 `car_id`가 같아야 한다.

처리:

- Redis `parking_fee_quote:{session_id}`를 먼저 조회한다.
- quote가 있으면 그대로 반환한다.
- quote가 없으면 DB `parking_sessions`에서 active session을 조회한다.
- PMS에 현재 요금을 요청한다.
- PMS 결과를 Redis `parking_fee_quote:{session_id}`에 TTL 15분으로 저장한다.
- 요금 정보를 반환한다.

Redis 변경:

- `parking_fee_quote:{session_id}` 저장

DB 변경:

- 없음

외부 호출:

- PMS fee API

실패 케이스:

- 인증 실패
- session 없음
- session이 active가 아님
- session 소유 차량 불일치
- PMS fee 조회 실패

먼저 작성할 테스트:

- Redis quote가 있으면 PMS를 호출하지 않는다.
- Redis quote가 없으면 PMS를 호출하고 quote를 저장한다.
- 다른 차량의 session이면 403을 반환한다.
- active session이 아니면 404를 반환한다.

## UC-PAY-002. 결제 요청 처리

API:

- `POST /payment`

입력:

- Bearer app access token
- `session_id`
- `amount`
- `currency`

출력:

- 성공 시 `status=success`, `tx_id`, `approval_no`
- 실패 시 `status=failed`, `tx_id`, `failed_reason`

사전 조건:

- app access token이 유효해야 한다.
- Redis `parking_fee_quote:{session_id}`가 존재해야 한다.
- 요청 금액과 quote 금액이 일치해야 한다.
- DB `parking_sessions`에 active session이 있어야 한다.
- session의 `car_id`와 token의 `car_id`가 같아야 한다.
- 차량에 active billing key가 있어야 한다.

처리:

- token에서 `car_id`를 확인한다.
- fee quote를 조회하고 amount, currency를 검증한다.
- active parking session을 조회한다.
- active billing key를 조회한다.
- `idempotency_key = SHA-256(session_id + car_id + amount + currency)`를 생성한다.
- 같은 idempotency_key의 transaction이 success이면 기존 성공 결과를 반환한다.
- pending transaction이 있으면 현재 처리 상태를 반환하거나 PG 재시도를 정책에 따라 수행한다.
- transaction이 없으면 `transactions`에 pending row를 생성한다.
- Mock PG에 billing payment를 요청한다.
- PG 성공이면 transaction을 success로 업데이트한다.
- parking session을 completed로 업데이트한다.
- PMS에 payment complete를 통보한다.
- 앱 알림용 message를 발행한다.
- 성공 결과를 반환한다.

Redis 변경:

- 필요 시 `parking_fee_quote:{session_id}` 삭제 또는 유지

DB 변경:

- `transactions` insert pending
- `transactions` update success 또는 failed
- 성공 시 `parking_sessions` update completed

외부 호출:

- Mock PG billing payment API
- PMS payment complete API
- MQTT publish

실패 케이스:

- quote 없음 또는 만료
- amount/currency 불일치
- session 없음
- session 소유 차량 불일치
- active billing key 없음
- PG 결제 실패
- PMS paid notify 실패

먼저 작성할 테스트:

- quote 금액과 요청 금액이 같으면 pending transaction을 만들고 PG를 호출한다.
- PG 성공이면 transaction success, parking session completed가 된다.
- PG 실패이면 transaction failed, parking session active가 유지된다.
- 같은 idempotency_key로 재요청하면 중복 결제하지 않고 기존 결과를 반환한다.
- quote가 만료되면 409 또는 재조회 필요 오류를 반환한다.
- billing key가 없으면 PG를 호출하지 않는다.

## UC-PAY-003. 결제 완료 PMS 통보

API:

- 내부 client 호출: PMS `POST /payment/complete`

입력:

- Header `X-Webhook-Timestamp`
- Header `X-Webhook-Signature`
- `pms_session_id`
- `carpay_parking_session_id`
- `carpay_tx_id`
- `amount`
- `currency`
- `approval_no`
- `idempotency_key`

출력:

- PMS `status=success`

사전 조건:

- Car Pay-in transaction이 success 상태여야 한다.
- PMS가 검증할 수 있는 payment complete webhook signature가 있어야 한다.
- timestamp는 PMS 기준 5분 허용 오차 안에 있어야 한다.

처리:

- Car Pay-in Backend가 raw request body 기준으로 `HMAC-SHA256(PMS_WEBHOOK_SECRET, "{timestamp}.{sha256(raw_body)}")`를 생성한다.
- PMS에 결제 완료 body와 `X-Webhook-Timestamp`, `X-Webhook-Signature`를 함께 통보한다.
- PMS는 같은 방식으로 signature를 검증한 뒤 결제 완료를 기록한다.
- PMS 응답을 확인한다.
- 실패 시 재시도 대상 이벤트로 기록한다.

DB 변경:

- Car Pay-in DB 직접 변경 없음
- PMS DB `payment_requests` 변경은 PMS 책임

외부 호출:

- PMS payment complete API

실패 케이스:

- signature 불일치 또는 timestamp 만료
- PMS timeout
- PMS 5xx
- PMS idempotency conflict

먼저 작성할 테스트:

- 결제 성공 후 PMS paid notify payload가 정확히 생성된다.
- PMS paid notify에 공통 webhook signature header가 포함된다.
- PMS 실패 시 결제 성공 자체는 보존되고 재시도 가능 상태가 남는다.
- 같은 idempotency_key로 PMS 통보가 중복되어도 안전하다.

