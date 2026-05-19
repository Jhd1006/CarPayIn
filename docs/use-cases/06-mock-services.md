# 06. Mock Service Use Cases

## UC-PMS-001. 차량번호 사전 등록

서비스:

- Mock PMS

API:

- `POST /parking/pre-register`

처리:

- `lot_id`, `plate`를 사전 등록 상태로 저장한다.
- 중복 등록이면 기존 등록을 재사용한다.

먼저 작성할 테스트:

- 유효한 plate를 사전 등록한다.
- 같은 plate와 lot_id 중복 요청은 멱등 처리된다.

## UC-PMS-002. LPR 입차 이벤트로 PMS 세션 생성

서비스:

- Mock PMS

처리:

- LPR이 plate를 감지하면 PMS DB `parking_sessions`에 active 세션을 만든다.
- Car Pay-in Backend에 entry webhook을 보낸다.

먼저 작성할 테스트:

- active PMS session을 생성한다.
- 같은 plate에 active session이 있으면 중복 생성하지 않는다.
- webhook payload에 `pms_session_id`, `lot_id`, `plate`, `entry_time`이 포함된다.

## UC-PMS-003. 현재 요금 계산

서비스:

- Mock PMS

API:

- `GET /parking/fee`

처리:

- active PMS session을 찾는다.
- 입차 시간과 요금 정책으로 amount, duration을 계산한다.

먼저 작성할 테스트:

- active session이면 amount와 duration을 반환한다.
- session이 없으면 404를 반환한다.

## UC-PMS-004. 결제 완료 기록

서비스:

- Mock PMS

API:

- `POST /payment/complete`

처리:

- PMS DB `payment_requests`에 success 이력을 저장한다.
- idempotency_key로 중복 저장을 막는다.

먼저 작성할 테스트:

- 결제 완료 요청을 success로 저장한다.
- 같은 idempotency_key 재요청은 기존 결과를 반환한다.

## UC-PG-001. 카드 등록 WebView 완료와 billing key 발급

서비스:

- Mock PG

처리:

- 사용자가 WebView에서 카드 정보를 입력한다.
- Mock Card에 카드 검증과 token 생성을 요청한다.
- 받은 card_token으로 Mock PG DB `billing_keys`를 생성한다.
- Car Pay-in Backend에 card webhook을 보낸다.

먼저 작성할 테스트:

- 카드 검증 성공이면 billing_key를 저장한다.
- 같은 order_id는 billing_key를 중복 생성하지 않는다.
- 카드 검증 실패면 webhook 성공을 보내지 않는다.

## UC-PG-002. billing key 결제 승인

서비스:

- Mock PG

API:

- `POST /payments/billing`

처리:

- idempotency_key 중복 여부를 확인한다.
- billing key가 active인지 확인한다.
- billing key로 card_token을 찾는다.
- Mock Card에 승인 요청을 보낸다.
- 승인 성공이면 PG transaction을 success로 업데이트한다.
- 승인 실패이면 failed로 업데이트한다.

먼저 작성할 테스트:

- active billing_key면 카드 승인 후 success를 반환한다.
- 같은 idempotency_key 재요청은 기존 결과를 반환한다.
- inactive billing_key면 failed를 반환한다.

## UC-CARDCO-001. 카드 검증과 card token 발급

서비스:

- Mock Card

처리:

- 카드번호, 유효기간, CVC를 검증한다.
- 카드 정보를 암호화 또는 HMAC 처리해 저장한다.
- card_token을 발급한다.

먼저 작성할 테스트:

- 유효한 카드면 card_token과 last_four를 반환한다.
- 만료 카드면 실패한다.
- 같은 사용자와 카드의 중복 등록은 기존 카드 또는 token 정책에 따라 처리된다.

## UC-CARDCO-002. card token 결제 승인

서비스:

- Mock Card

처리:

- card_token이 active인지 확인한다.
- amount가 유효한지 확인한다.
- idempotency_key 중복을 확인한다.
- 카드사 tx를 생성하고 approval_no를 반환한다.

먼저 작성할 테스트:

- active card_token이면 success tx를 저장한다.
- 같은 idempotency_key 재요청은 기존 tx를 반환한다.
- inactive card_token이면 failed를 반환한다.

