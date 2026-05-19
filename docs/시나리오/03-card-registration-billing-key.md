# 03. 카드 등록 / Billing Key 저장

관련 다이어그램: `docs/diagrams/lucid-03-card-registration-billing-key.mmd`

## 이 단계의 목적

차량에 결제수단을 연결해서 자동결제가 가능한 상태로 만드는 단계다.

중요한 점은 Car Pay-in이 카드번호, CVC 같은 카드 원본 정보를 직접 저장하지 않는다는 것이다. 사용자는 Mock PG WebView에 카드 정보를 입력하고, Car Pay-in은 PG가 발급한 `billing_key`만 저장한다.

## 등장하는 참여자

- 사용자: 앱에서 카드 등록을 시작하고 WebView에 카드 정보를 입력한다.
- AAOS App: 번호판, 카드사, 동의 여부를 백엔드로 보내고 PG WebView를 연다.
- Car Pay-in Backend: 차량/번호판/소유주를 검증하고, PG 웹훅을 받아 billing key를 저장한다.
- Redis: 카드 등록 order 상태를 임시 저장한다.
- MOLIT API: 차량 번호판과 소유주가 맞는지 검증한다.
- Mock PG: 카드 등록 화면을 제공하고 billing key를 발급한다.
- Mock PG DB: billing key와 PG 결제 이력을 저장한다.
- Mock Card: 카드 검증과 카드 승인 역할을 한다.
- Mock Card DB: 카드 token과 카드사 기준 거래 이력을 저장한다.
- Car Pay-in DB: 차량별 현재 billing key를 저장한다.

## 핵심 개념

`order_id`는 카드 등록 요청을 구분하는 ID다. 백엔드는 `mock_pg_card_register:{order_id}`에 "이 카드 등록 요청은 어떤 차량의 요청인지"를 저장한다.

`billing_key`는 PG가 발급하는 결제용 키다. Car Pay-in은 카드번호 대신 이 키를 저장하고, 나중에 결제할 때 이 키를 사용한다.

`vehicle_billing_keys`는 차량별 현재 결제수단을 저장하는 테이블이다. 차량 1대는 현재 사용할 active billing key 1개를 가진다.

## 단계별 흐름

1. 사용자가 앱에서 카드 등록을 시작한다.
2. 앱은 개인정보/결제 등록 동의를 받고, 번호판과 카드사를 입력받는다.
3. 앱은 `/card/order`로 `plate`, `bank_name`, `agree_terms`를 백엔드에 보낸다.
4. 백엔드는 access token으로 현재 차량을 확인하고, `vehicles`에서 차량 등록 상태를 조회한다.
5. 백엔드는 번호판 형식이 올바른지 확인한다.
6. 백엔드는 MOLIT API로 번호판, 차량, 소유주가 일치하는지 검증한다.
7. 검증이 통과하면 백엔드는 `order_id`를 만들고 Redis에 `mock_pg_card_register:{order_id}`를 저장한다.

```json
{
  "order_id": "...",
  "user_id": "...",
  "car_id": "...",
  "status": "pending",
  "created_at": "...",
  "expires_at": "..."
}
```

8. 백엔드는 앱에 Mock PG WebView URL을 반환한다.
9. 앱은 WebView로 Mock PG 카드 등록 화면을 연다.
10. 사용자는 WebView에서 카드번호, 유효기간, CVC를 입력한다.
11. Mock PG는 카드 정보를 Mock Card에 보내 검증한다.
12. Mock Card는 카드 정보를 검증하고, 카드 원본 대신 `card_token`을 만든다.
13. Mock Card DB에는 카드 token과 카드 검증 결과가 저장된다.
14. Mock PG는 `card_token`을 기반으로 `billing_key`를 만들고 Mock PG DB의 `billing_keys`에 저장한다.
15. Mock PG는 카드 등록 완료 웹훅을 Car Pay-in Backend로 보낸다.
16. 백엔드는 웹훅의 HMAC을 검증해서 신뢰할 수 있는 PG 요청인지 확인한다.
17. 백엔드는 Redis의 `mock_pg_card_register:{order_id}`를 조회해서 이 order가 어떤 차량의 요청인지 확인한다.
18. 백엔드는 `vehicle_billing_keys`에 차량별 billing key와 카드 뒤 4자리를 저장하거나 갱신한다.
19. 백엔드는 사용이 끝난 `mock_pg_card_register:{order_id}`를 Redis에서 삭제한다.
20. PG는 앱 WebView에 카드 등록 완료를 알려주고, 앱은 `registered=true` 상태로 전환한다.

## 이 단계가 끝나면 남는 데이터

Redis:

- `mock_pg_card_register:{order_id}`: 카드 등록 중에만 존재하고, 웹훅 처리 후 삭제된다.

Car Pay-in DB:

- `vehicle_billing_keys`: 차량별 현재 active billing key

Mock PG DB:

- `billing_keys`: PG가 발급한 billing key와 card token 매핑

Mock Card DB:

- `cards`, `card_tokens`: 카드사 기준 카드 정보와 token

## 발표 멘트

세 번째 단계는 차량에 결제수단을 연결하는 과정입니다. 앱은 번호판과 카드사를 백엔드에 보내고, 백엔드는 차량 등록 상태와 소유주 검증을 먼저 수행합니다. 검증이 끝나면 Redis에 카드 등록 order를 저장하고 PG WebView URL을 내려줍니다. 사용자의 카드 입력은 Car Pay-in을 거치지 않고 Mock PG와 Mock Card에서 처리됩니다. 최종적으로 Car Pay-in은 카드 원본이 아니라 PG가 발급한 `billing_key`만 `vehicle_billing_keys`에 저장합니다.
