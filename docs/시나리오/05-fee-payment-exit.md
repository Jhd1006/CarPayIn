# 05. 요금 조회 / 결제 / 출차

관련 다이어그램: `docs/diagrams/lucid-05-fee-payment-exit.mmd`

## 이 단계의 목적

주차 중인 차량이 출차 전에 요금을 조회하고, 사용자가 승인하면 등록된 billing key로 결제를 처리하는 단계다.

이 단계에서는 결제 요청을 먼저 `pending` 상태로 기록하고, PG 승인 결과에 따라 `success` 또는 `failed`로 확정한다. 결제 성공 후에는 PMS에 paid 상태를 전달해서 출구 차단기가 열릴 수 있게 한다.

## 등장하는 참여자

- 사용자: 차량 화면에서 요금을 확인하고 결제를 승인한다.
- AAOS App: 시동 ON과 `parked=true` 상태를 감지하고 요금 조회/결제 요청을 보낸다.
- Car Pay-in Backend: 요금 quote를 검증하고, 결제 이력을 만들고, PG와 PMS를 호출한다.
- Redis: 짧은 시간 동안 유효한 요금 quote를 저장한다.
- Car Pay-in DB: 주차 세션, 차량별 billing key, 결제 이력을 저장한다.
- Parking PMS: 현재 요금을 계산하고, 결제 완료 통보를 받는다.
- Mock PG: billing key 기반 결제를 처리한다.
- Mock PG DB: PG 기준 거래 이력과 idempotency key를 저장한다.
- Mock Card: card token으로 카드 승인 요청을 처리한다.
- Mock Card DB: 카드사 기준 거래 이력을 저장한다.

## 핵심 개념

`parking_fee_quote:{session_id}`는 앱에 보여준 요금이 결제 요청 시에도 같은지 검증하기 위한 Redis key다. 요금은 시간이 지나면 바뀔 수 있으므로 짧은 TTL로 관리한다.

`transactions`는 Car Pay-in 기준 결제 이력이다. 결제 요청이 들어오면 먼저 `pending` 상태로 만들고, PG 결과에 따라 `success` 또는 `failed`로 업데이트한다.

`idempotency_key`는 같은 결제 요청이 중복 처리되는 것을 막기 위한 키다. 네트워크 재시도나 버튼 중복 클릭이 있어도 같은 키면 PG와 DB에서 중복 결제를 막을 수 있다.

## 단계별 흐름

1. 사용자가 차량에 탑승하고 시동을 켜면 앱의 백그라운드 서비스가 깨어난다.
2. 앱은 로컬 저장소의 `parked` 값을 확인한다.
3. `parked=false`면 주차 중이 아니므로 아무것도 하지 않는다.
4. `parked=true`면 앱은 저장된 `session_id`, `lot_id`를 기준으로 백엔드에 요금 조회를 요청한다.
5. 백엔드는 Redis의 `parking_fee_quote:{session_id}`를 먼저 조회한다.
6. quote가 있으면 그 값을 앱에 반환한다.
7. quote가 없으면 백엔드는 Car Pay-in DB의 `parking_sessions`에서 active 세션을 조회한다.
8. 백엔드는 PMS에 현재 주차 요금을 요청한다.
9. PMS는 입차 시각과 요금 정책을 기준으로 amount와 duration을 계산해 반환한다.
10. 백엔드는 이 결과를 Redis의 `parking_fee_quote:{session_id}`에 저장한다.

```json
{
  "session_id": "...",
  "pms_session_id": "...",
  "car_id": "...",
  "lot_id": "...",
  "plate": "...",
  "amount": 6000,
  "currency": "KRW",
  "created_at": "...",
  "expires_at": "..."
}
```

11. 앱은 요금 정보를 사용자에게 보여준다.
12. 사용자가 결제를 승인하면 앱은 `/payment`로 `session_id`, `amount`, `currency`를 보낸다.
13. 백엔드는 Redis의 `parking_fee_quote:{session_id}`를 조회해서 앱이 보낸 금액과 통화가 직전 quote와 같은지 검증한다.
14. 백엔드는 `parking_sessions`에서 active 세션을 조회한다.
15. 백엔드는 `vehicle_billing_keys`에서 차량의 active billing key를 조회한다.
16. 백엔드는 `transactions`에 결제 요청을 `pending` 상태로 먼저 저장한다.
17. 백엔드는 idempotency key와 billing key를 포함해 Mock PG에 결제를 요청한다.
18. Mock PG는 Mock PG DB에서 idempotency key 중복 여부를 확인한다.
19. 중복 요청이면 기존 결과를 반환하고, 신규 요청이면 PG 기준 거래를 생성한다.
20. Mock PG는 billing key로 card token을 찾고, Mock Card에 카드 승인을 요청한다.
21. Mock Card는 카드사 기준 거래 `tx`를 저장하고 승인번호를 반환한다.
22. Mock PG는 PG 기준 거래를 `success`로 업데이트하고 `pg_tx_id`, `approval_no`를 백엔드에 반환한다.
23. 백엔드는 Car Pay-in DB의 `transactions`를 `success`로 업데이트한다.
24. 백엔드는 `parking_sessions`를 `completed`로 업데이트한다.
25. 백엔드는 PMS에 paid 통보를 보낸다.
26. PMS는 PMS DB의 세션 또는 결제 요청 상태를 paid/success로 업데이트한다.
27. 앱은 결제 완료 응답을 받고 로컬 상태를 `parked=false`로 바꾼다.
28. 이후 차량이 출구에 도착하면 PMS는 자기 DB의 paid 상태를 보고 차단기를 열 수 있다.

## 이 단계가 끝나면 남는 데이터

Redis:

- `parking_fee_quote:{session_id}`: 결제 전 짧게 유지되는 요금 quote

Car Pay-in DB:

- `transactions`: Car Pay-in 기준 결제 이력
- `parking_sessions`: completed 상태로 변경된 주차 세션

Mock PG DB:

- `transactions`: PG 기준 결제 요청/승인 이력

Mock Card DB:

- `tx`: 카드사 기준 승인 이력

PMS DB:

- paid 또는 success 상태의 주차/결제 기록

앱 로컬 저장소:

- `parked=false`

## 발표 멘트

다섯 번째 단계는 요금 조회와 결제입니다. 앱은 시동 ON 시점에 `parked=true`인지 확인하고, 주차 중일 때만 백엔드에 요금 조회를 요청합니다. 백엔드는 Redis의 요금 quote를 먼저 확인하고, 없으면 DB의 주차 세션과 PMS 요금 정보를 기반으로 quote를 생성합니다. 사용자가 결제를 승인하면 백엔드는 quote와 금액을 검증하고, 결제 요청을 `transactions`에 pending으로 먼저 저장합니다. 이후 billing key로 PG 결제를 요청하고, 승인 결과가 오면 transaction을 success로 확정하고 주차 세션을 completed로 변경합니다. 마지막으로 PMS에 paid 상태를 알려 출구 차단기가 열릴 수 있게 합니다.
