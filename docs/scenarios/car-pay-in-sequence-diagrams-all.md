# Car Pay-in 시퀀스 다이어그램 5단계 설명

이 문서는 Notion에 한 번에 붙여넣거나 import하기 위한 합본이다.

---

# 01. QR 로그인 / 현대 OAuth

관련 다이어그램: `docs/diagrams/01-qr-oauth-login.mmd`

## 이 단계의 목적

사용자가 차량에서 Car Pay-in 등록을 시작했을 때, 스마트폰의 MyHyundai 로그인을 통해 "이 사용자가 누구인지" 확인하는 단계다.

차량 안의 AAOS 앱은 직접 현대 로그인을 처리하지 않는다. 대신 앱이 QR을 보여주고, 사용자가 스마트폰으로 QR을 스캔해서 MyHyundai OAuth 로그인을 진행한다.

## 등장하는 참여자

- 사용자: 차량 등록을 시작하고 스마트폰으로 QR을 스캔한다.
- AAOS App: `session_id`와 `vin_hash`를 만들고 QR을 표시한다.
- 스마트폰 브라우저: QR URL을 열고 MyHyundai 로그인으로 이동한다.
- Car Pay-in Backend: QR 세션을 만들고 현대 OAuth 요청을 시작한다.
- Redis: QR 로그인 상태와 OAuth state 매핑을 임시 저장한다.
- MyHyundai OAuth API: 사용자 로그인과 authorization code 발급을 담당한다.
- Car Pay-in DB: 현대 사용자 정보를 저장한다. 현대 access/refresh token은 저장하지 않는다.

## 핵심 개념

`session_id`는 AAOS 앱이 만든 QR 로그인 세션 ID다. 앱과 백엔드가 "지금 차량에서 시작된 이 로그인 요청"을 추적하기 위해 사용한다.

`vin_hash`는 차량 VIN 원문을 직접 노출하지 않기 위해 만든 해시값이다. 앱은 `sha256(VIN + session_id)`로 해싱한다. `session_id`를 함께 섞어 해싱하기 때문에 세션마다 다른 값이 나와 재사용 공격을 차단한다. `vin_hash`는 QR URL에 포함하지 않는다. QR 코드는 공개된 값이므로 노출되면 안 되고, QR 세션 생성 시점에 이미 백엔드 Redis에 저장해두기 때문에 URL에 실을 필요가 없다.

`oauth_state`는 백엔드가 새로 만든 일회용 랜덤값이다. 현대 OAuth URL의 `state` 파라미터에는 내부 `session_id`를 그대로 넣지 않고, `oauth_state`만 넣는다. 백엔드는 Redis에 `oauth_state -> session_id` 매핑을 저장해두고, 현대 callback이 돌아오면 이 값을 조회해서 원래 QR 세션을 찾는다.

## 단계별 흐름

1. 사용자가 AAOS 앱에서 차량 등록을 시작한다.
2. 앱은 `session_id`를 만들고, 차량 VIN을 기반으로 `vin_hash`를 만든다.
3. 앱은 QR을 표시하기 전에 백엔드 `POST /auth/qr-session`으로 `session_id`와 `vin_hash`를 보낸다.
4. 백엔드는 Redis에 `qr_session:{session_id}`를 저장하고, 앱에 QR로 표시할 `login_url`을 반환한다.
5. 앱은 다음 형태의 QR URL을 화면에 표시한다.

```text
/auth/hyundai/start?session_id={session_id}
```

6. 사용자가 스마트폰으로 QR을 스캔하면 스마트폰 브라우저가 백엔드의 `/auth/hyundai/start`로 들어온다.
7. 백엔드는 Redis의 `qr_session:{session_id}`가 존재하고 `pending` 상태인지 확인한다.

```json
{
  "vin_hash": "...",
  "status": "pending",
  "created_at": "...",
  "expires_at": "..."
}
```

8. 백엔드는 `oauth_state`라는 별도 랜덤값을 만들고 Redis에 `oauth_state:{oauth_state}`를 저장한다.

```json
{
  "session_id": "...",
  "status": "pending",
  "created_at": "...",
  "expires_at": "..."
}
```

9. 백엔드는 현대 OAuth 로그인 URL로 사용자를 redirect한다. 이때 현대에 넘기는 `state` 값은 `session_id`가 아니라 `oauth_state`다.
10. 사용자가 MyHyundai 로그인을 완료하면 현대 OAuth API가 백엔드 callback으로 authorization code와 state를 돌려준다.
11. 백엔드는 state 값으로 Redis의 `oauth_state`를 조회해서 원래 `session_id`를 찾는다.
12. 백엔드는 authorization code를 현대 token API에 보내 현대 access token과 refresh token을 받는다.
13. 백엔드는 현대 access token으로 사용자 정보와 차량 목록을 즉시 조회한다.
14. 백엔드는 현대 사용자 정보를 `users`에 저장하거나 갱신한다.
15. 현대 access/refresh token은 이 시점 이후 사용하지 않으며 Redis나 DB에 저장하지 않는다.
16. 백엔드는 차량 확정용 임시 app access token을 발급한다.
17. 백엔드는 사용자 정보, 차량 목록, 임시 app access token을 Redis `hyundai_oauth:{session_id}`와 `app_login_result:{session_id}`에 저장한다.

## 이 단계가 끝나면 남는 데이터

Redis:

- `qr_session:{session_id}`: QR 로그인 진행 상태와 `vin_hash`
- `oauth_state:{oauth_state}`: 현대 OAuth callback을 원래 `session_id`에 연결하기 위한 매핑
- `hyundai_oauth:{session_id}`: 차량 확정 전 내부 조회용 OAuth 임시 결과
- `app_login_result:{session_id}`: AAOS 앱 polling용 로그인 완료 결과

Car Pay-in DB:

- `users`: 현대 로그인 기준 사용자 정보

저장하지 않는 데이터:

- 현대 access token
- 현대 refresh token
- Redis `hyundai_access:{user_id}`
- DB `hyundai_tokens`

## 발표 멘트

첫 번째 단계는 차량에서 시작된 QR 로그인 요청을 스마트폰의 현대 OAuth 로그인과 연결하는 과정입니다. 앱은 `session_id`와 `vin_hash`를 만들고, QR을 표시하기 전에 먼저 백엔드에 `vin_hash`를 전송해 Redis에 저장합니다. QR URL에는 `session_id`만 담아 공개 노출을 최소화합니다. 백엔드는 현대 OAuth로 이동할 때 내부 `session_id`를 직접 넘기지 않고 일회용 `oauth_state`를 사용합니다. OAuth callback이 돌아오면 백엔드는 현대 토큰으로 사용자 정보와 차량 목록을 동기 조회한 뒤 즉시 버립니다. 사용자 정보는 DB에 저장하고, 차량 목록과 임시 app access token은 Redis에 보관해 앱이 polling으로 확인할 수 있게 합니다.


---

# 02. 차량 선택 / 차량 등록

관련 다이어그램: `docs/diagrams/02-vehicle-confirmation.mmd`

## 이 단계의 목적

현대 OAuth callback에서 이미 조회된 차량 목록 중 Car Pay-in에 연결할 차량을 확정하는 단계다.

이 단계가 끝나면 Car Pay-in DB에 "이 사용자의 이 차량을 서비스에 등록했다"는 정보가 남는다. 다만 아직 결제수단은 연결되지 않았으므로 자동결제 가능 상태는 아니다.

## 등장하는 참여자

- AAOS App: 로그인 완료 여부를 polling하고, 사용자가 차량을 선택하게 한다.
- Car Pay-in Backend: Redis의 로그인 완료 결과를 검증하고, 선택된 차량을 DB에 저장한다.
- Redis: 현대 OAuth 결과와 앱에 내려줄 로그인 결과를 임시 저장한다.
- Car Pay-in DB: 확정된 차량과 앱 refresh token을 저장한다.

## 핵심 개념

`hyundai_oauth:{session_id}`는 현대 OAuth callback에서 얻은 결과를 잠깐 보관하는 Redis key다. 사용자 정보, 차량 목록, 차량 확정용 임시 app access token이 들어간다. 현대 access/refresh token은 들어가지 않는다.

`app_login_result:{session_id}`는 AAOS 앱이 polling으로 가져갈 로그인 완료 결과다. 차량 확정용 임시 access token, 사용자 ID, 사용자 이름, 차량 목록이 들어간다.

`vehicles`는 실제 서비스에 등록된 차량 정보의 source of truth다. 사용자가 차량을 확정해야 이 테이블에 저장된다.

## 단계별 흐름

1. 현대 OAuth callback이 성공하면 백엔드는 차량 목록과 임시 app access token을 `app_login_result:{session_id}`에 저장한다.
2. AAOS 앱은 QR 화면에서 주기적으로 `/auth/session/{session_id}/status`를 호출한다.
3. 아직 완료되지 않았으면 백엔드는 `pending` 또는 `agreement_required`를 반환한다.
4. 완료되면 백엔드는 차량 확정용 임시 app access token과 차량 목록을 반환한다.
5. 차량이 1대면 앱은 자동으로 선택할 수 있고, 여러 대면 사용자가 직접 차량을 선택한다.
6. 앱은 `/auth/confirm-car`로 선택된 `car_id`를 백엔드에 보낸다.
7. 백엔드는 임시 app access token과 `app_login_result:{session_id}`를 검증한다.
8. 백엔드는 선택된 `car_id`가 OAuth callback에서 받은 차량 목록 안에 실제로 있는지 확인한다.
9. 검증이 통과하면 `vehicles` 테이블에 차량 정보를 저장하거나 갱신한다.
10. 앱 refresh token은 원문을 저장하지 않고 hash로 만들어 `app_refresh_tokens`에 저장한다.
11. 백엔드는 최종 앱 access token, refresh token과 함께 차량 확정 완료를 응답한다.

## 이 단계가 끝나면 남는 데이터

Redis:

- `hyundai_oauth:{session_id}`: 현대 OAuth/Data API 결과 임시 저장
- `app_login_result:{session_id}`: AAOS 앱 polling용 로그인 완료 결과

Car Pay-in DB:

- `vehicles`: 서비스에 등록된 차량 정보
- `app_refresh_tokens`: 앱 refresh token hash와 만료 정보

## 발표 멘트

두 번째 단계는 현대 OAuth callback에서 이미 가져온 차량 목록 중 실제로 Car Pay-in에 연결할 차량을 확정하는 과정입니다. 앱은 polling을 통해 로그인 완료 결과와 차량 목록을 받고, 사용자가 차량을 선택하면 백엔드는 그 차량이 callback 결과에 포함된 차량인지 검증한 뒤 `vehicles`에 저장합니다. 이 시점에는 차량 연동만 끝난 상태이고, 결제수단은 아직 연결되지 않았습니다.


---

# 03. 카드 등록 / Billing Key 저장

관련 다이어그램: `docs/diagrams/03-card-registration-billing-key.mmd`

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

8. 백엔드는 PG internal API에 `order_id`를 보내 Mock PG WebView URL 생성을 요청한다.
9. Mock PG는 `order_id`가 포함된 public WebView URL을 반환한다.
10. 백엔드는 앱에 `order_id`와 Mock PG WebView URL을 반환한다.
11. 앱은 WebView로 Mock PG 카드 등록 화면을 연다.
12. 사용자는 WebView에서 카드번호, 유효기간, CVC를 입력한다.
13. Mock PG는 카드 정보를 Mock Card에 보내 검증한다.
14. Mock Card는 카드 정보를 검증하고, 카드 원본 대신 `card_token`을 만든다.
15. Mock Card DB에는 카드 token과 카드 검증 결과가 저장된다.
16. Mock PG는 `card_token`을 기반으로 `billing_key`를 만들고 Mock PG DB의 `billing_keys`에 저장한다.
17. Mock PG는 카드 등록 완료 웹훅 body를 만들고 `PG_WEBHOOK_SECRET`으로 `X-Webhook-Timestamp`, `X-Webhook-Signature`를 생성한다.
18. Mock PG는 카드 등록 완료 웹훅을 Car Pay-in Backend로 보낸다.
19. 백엔드는 같은 raw body와 timestamp로 HMAC을 다시 계산해 신뢰할 수 있는 PG 요청인지 확인한다.
20. 백엔드는 Redis의 `mock_pg_card_register:{order_id}`를 조회해서 이 order가 어떤 차량의 요청인지 확인한다.
21. 백엔드는 `vehicle_billing_keys`에 차량별 billing key와 카드 뒤 4자리를 저장하거나 갱신한다.
22. 백엔드는 사용이 끝난 `mock_pg_card_register:{order_id}`를 Redis에서 삭제한다.
23. PG는 앱 WebView에 카드 등록 완료를 알려주고, 앱은 `registered=true` 상태로 전환한다.

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

세 번째 단계는 차량에 결제수단을 연결하는 과정입니다. 앱은 번호판과 카드사를 백엔드에 보내고, 백엔드는 차량 등록 상태와 소유주 검증을 먼저 수행합니다. 검증이 끝나면 Redis에 카드 등록 order를 저장하고 PG internal API에서 WebView URL을 받아 앱에 내려줍니다. 사용자의 카드 입력은 Car Pay-in을 거치지 않고 Mock PG와 Mock Card에서 처리됩니다. 최종적으로 Car Pay-in은 카드 원본이 아니라 PG가 발급한 `billing_key`만 `vehicle_billing_keys`에 저장합니다.


---

# 04. 입차 사전알림 / 주차 세션 생성

관련 다이어그램: `docs/diagrams/04-entry-parking-session.mmd`

## 이 단계의 목적

차량이 주차장에 들어가기 전에 PMS에 번호판을 미리 알려두고, 실제 입차가 발생하면 Car Pay-in 기준 주차 세션을 생성하는 단계다.

입차 시에는 결제를 하지 않는다. 이 단계의 핵심은 "이 차량이 Car Pay-in 자동결제 대상 차량으로 입차했다"는 세션을 만드는 것이다.

## 등장하는 참여자

- AAOS App: 앱 내 제휴 주차장 목록에서 길안내 버튼을 눌러 사전알림을 보낸다.
- Car Pay-in Backend: 차량과 billing key를 검증하고 사전알림 상태를 저장한다.
- carpayin-redis: `parking_pre_notify:{lot_id}:{plate}` 사전알림 상태를 임시 저장한다.
- Car Pay-in DB: Car Pay-in 기준 주차 세션을 저장한다.
- Parking PMS: 주차장 현장 시스템 역할을 하며 번호판 사전 등록과 LPR 이벤트를 처리한다.
- pms-redis: `pre_reg:{lot_id}:{plate}` 사전등록 차량번호를 임시 저장한다.
- PMS DB: PMS 기준 입차 세션 정보를 저장한다.
- LPR Camera: 입구에서 번호판을 인식한다.

## 핵심 개념

`parking_pre_notify:{lot_id}:{plate}`는 "이 번호판 차량이 곧 이 주차장에 들어올 예정이고, Car Pay-in에 등록된 차량이다"라는 임시 상태다. `car_id`, `user_id`를 포함해 PMS webhook 수신 시 세션 생성에 활용된다.

`pre_reg:{lot_id}:{plate}`는 PMS Redis에만 저장되는 단순 존재 여부 키다. 값은 `"1"`, LPR 입차 시 해당 번호판이 사전 등록된 Car Pay-in 차량인지 판단하는 데만 사용한다.

PMS DB의 주차 세션과 Car Pay-in DB의 주차 세션은 서로 다른 시스템의 데이터다. 두 시스템은 `pms_session_id`, `lot_id`, `plate` 같은 값으로 논리적으로 연결된다.

## 단계별 흐름

1. 사용자가 앱에서 `GET /parking/lots`로 제휴 주차장 목록을 조회한다.
2. 원하는 주차장의 길안내 버튼을 탭한다.
3. 앱은 `POST /parking/navigate`로 `lot_id`만 백엔드에 보낸다.
4. 백엔드는 access token에서 `car_id`와 `user_id`를 추출한다.
5. 백엔드는 `vehicles`에서 차량과 번호판을 조회한다.
6. 백엔드는 `vehicle_billing_keys`에서 active billing key가 있는지 확인한다.
7. 검증이 통과하면 carpayin-redis에 `parking_pre_notify:{lot_id}:{plate}`를 저장한다 (TTL 1시간).

```json
{
  "user_id": "...",
  "car_id": "...",
  "lot_id": "...",
  "plate": "...",
  "status": "incoming",
  "created_at": "...",
  "expires_at": "..."
}
```

8. 백엔드는 PMS에 `POST /parking/pre-register`로 번호판 사전 등록을 요청한다.
9. PMS는 pms-redis에 `pre_reg:{lot_id}:{plate} = "1"`을 저장한다 (TTL 1시간).
10. 실제 차량이 입구에 도착하면 LPR Camera가 번호판을 인식한다.
11. PMS는 번호판 인식 즉시 입구 차단기를 연다. Car Pay-in 사용자인지와 무관하게 모든 차량에 적용한다.
12. PMS는 PMS DB에 `parking_sessions`를 생성한다 (`status=active`). 모든 차량 대상.
13. PMS는 pms-redis에 `parking_session:{lot_id}:{plate}`를 `status=active`로 저장한다 (TTL 72시간). 출차 판단에 사용하는 실시간 상태판이다.
14. PMS는 pms-redis에서 `pre_reg:{lot_id}:{plate}` 키를 조회한다.
15. 키가 존재하면 키를 삭제한다. 키가 없으면 webhook을 보내지 않는다.
16. PMS는 입차 이벤트 raw body를 만들고 `PMS_WEBHOOK_SECRET`으로 `X-Webhook-Timestamp`, `X-Webhook-Signature`를 생성한다.
17. PMS는 Car Pay-in Backend에 `POST /webhook/entry`로 입차 이벤트를 보낸다.
18. 백엔드는 같은 raw body와 timestamp로 HMAC을 다시 계산해 신뢰할 수 있는 PMS 요청인지 확인한다.
19. 백엔드는 carpayin-redis의 `parking_pre_notify:{lot_id}:{plate}`를 조회해 `car_id`를 가져온다.
20. 백엔드는 Car Pay-in DB의 `parking_sessions`에 서비스 기준 주차 세션을 생성한다.
21. 백엔드는 사용이 끝난 `parking_pre_notify:{lot_id}:{plate}`를 삭제한다.
22. 백엔드는 결제 완료 이벤트를 AWS SQS에 발행한다. SQS → Lambda → AWS IoT Core 경로로 앱에 입차 알림이 Push된다 (로컬 개발 시에는 paho-mqtt로 Mosquitto에 직접 발행).
23. 앱은 입차 알림을 받고 로컬 상태를 `parked=true`로 저장한다.

## 이 단계가 끝나면 남는 데이터

carpayin-redis:

- `parking_pre_notify:{lot_id}:{plate}`: 입차 webhook 처리 후 삭제된다.

pms-redis:

- `pre_reg:{lot_id}:{plate}`: LPR 입차 시 consume 후 삭제된다. TTL 1시간 자동 만료.
- `parking_session:{lot_id}:{plate}`: LPR 입차 시 생성. `status=active`. TTL 72시간. 결제 완료 시 `paid`로 갱신, 출차 확인 후 삭제.

Car Pay-in DB:

- `parking_sessions`: Car Pay-in 기준 active 주차 세션

PMS DB:

- `parking_sessions`: PMS 기준 주차 세션 (`status=active`)

앱 로컬 저장소:

- `parked=true`
- `session_id`
- `lot_id`

## 발표 멘트

네 번째 단계는 입차 사전알림과 주차 세션 생성입니다. 사용자가 앱에서 제휴 주차장의 길안내 버튼을 누르면, 앱은 주차장 ID만 백엔드에 보냅니다. 백엔드는 토큰에서 차량 정보를 꺼내 검증한 뒤 두 Redis에 사전 등록 정보를 저장합니다. 실제 입차 시 LPR이 번호판을 인식하면 PMS는 모든 차량에 즉시 차단기를 열고 세션을 생성합니다. Car Pay-in 사전 등록 차량이면 백엔드에 webhook을 보내 앱 알림까지 이어집니다.


---

# 05. 요금 조회 / 결제 / 출차

관련 다이어그램: `docs/diagrams/05-fee-payment-exit.mmd`

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

`parking_fee_quote:{session_id}`는 앱에 보여준 요금이 결제 요청 시에도 같은지 검증하기 위한 Redis key다. 요금은 시간이 지나면 바뀔 수 있으므로 15분 TTL로 관리한다.

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
10. 백엔드는 이 결과를 Redis의 `parking_fee_quote:{session_id}`에 15분 TTL로 저장한다.

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
25. 백엔드는 PMS에 paid 통보를 보낸다 (`POST /payment/complete`).
26. PMS는 PMS DB의 `parking_sessions` 상태를 `paid`로, pms-redis `parking_session:{lot_id}:{plate}` 상태도 `paid`로 업데이트한다. 이 시점에 차단기는 열지 않는다.
27. 앱은 결제 완료 응답을 받고 로컬 상태를 `parked=false`로 바꾼다.
28. 백엔드는 결제 완료 이벤트를 AWS SQS에 발행한다. SQS → Lambda → AWS IoT Core 경로로 앱에 결제 완료 알림이 Push된다 (로컬 개발 시에는 paho-mqtt로 Mosquitto에 직접 발행).
29. 차량이 출구에 도착하면 출구 LPR이 번호판을 인식한다.
30. PMS는 pms-redis `parking_session:{lot_id}:{plate}`를 우선 조회한다. 상태가 `paid`이면 HTTP로 출구 차단기를 열고, Redis 키를 삭제하고, DB 세션을 `exited`로 변경한다. Redis 키가 없으면 DB fallback으로 조회한다. 미결제(`active`) 차량은 차단기를 열지 않는다.

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

- `parking_sessions`: 결제 완료 후 `paid`, 출차 LPR 확인 후 `exited` 상태
- `payment_requests`: PMS 기준 결제 완료 이력 (`status=success`)

앱 로컬 저장소:

- `parked=false`

## 발표 멘트

다섯 번째 단계는 요금 조회, 결제, 출차입니다. 앱은 시동 ON 시점에 `parked=true`인지 확인하고, 주차 중일 때만 백엔드에 요금 조회를 요청합니다. 백엔드는 Redis의 요금 quote를 먼저 확인하고, 없으면 DB의 주차 세션과 PMS 요금 정보를 기반으로 quote를 생성합니다. 사용자가 결제를 승인하면 백엔드는 quote와 금액을 검증하고, 결제 요청을 `transactions`에 pending으로 먼저 저장합니다. 이후 billing key로 PG 결제를 요청하고, 승인 결과가 오면 transaction을 success로 확정하고 주차 세션을 completed로 변경합니다. 백엔드는 PMS에 paid 통보를 보내고, PMS는 DB와 pms-redis 상태를 `paid`로 업데이트합니다. 동시에 백엔드는 SQS → Lambda → IoT Core 경로로 앱에 결제 완료 알림을 Push합니다. 이후 차량이 출구에 도착하면 PMS는 pms-redis를 우선 조회해 `paid` 상태이면 HTTP로 차단기를 열고, Redis 키를 삭제한 뒤 DB 세션을 `exited`로 전환합니다.

