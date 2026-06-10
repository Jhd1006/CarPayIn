# 04. Entry / Parking Session Use Cases

## UC-PARK-001. 제휴 주차장 길안내 → 사전 입차 알림 등록

트리거: 앱에서 제휴 주차장 목록(`GET /parking/lots`) 조회 후 원하는 주차장의 길안내 버튼 탭

API:

- `GET /parking/lots` — 제휴 주차장 목록 조회 (인증 불필요)
- `POST /parking/navigate` — 길안내 탭 시 사전 등록

입력:

- Bearer app access token (Authorization 헤더)
- `lot_id`: 길안내를 누른 주차장 ID

출력:

- `status=registered`
- `car_id`: 토큰에서 추출된 차량 ID
- `lot_id`: 요청한 주차장 ID
- `plate`: DB에서 조회한 차량번호

사전 조건:

- app access token이 유효해야 한다.
- 토큰의 `car_id`에 해당하는 차량이 DB `vehicles`에 존재해야 한다.
- 해당 차량에 번호판(`plate`)이 등록되어 있어야 한다.
- `vehicle_billing_keys`에 active billing key가 있어야 한다.

처리:

- Authorization 헤더의 access token을 검증하고 `car_id`, `user_id`를 추출한다.
- DB `vehicles`에서 `car_id`로 차량과 번호판을 조회한다.
- 차량이 없거나 번호판이 미등록이면 400 반환.
- `vehicle_billing_keys`에서 active billing key 존재 여부를 확인한다.
- carpayin-redis에 `parking_pre_notify:{lot_id}:{plate}`를 incoming 상태로 저장한다 (TTL 1시간).
- PMS에 `POST /parking/pre-register`로 `{ lot_id, plate }`를 전달해 pms-redis에 사전 등록한다.

Redis 변경:

- carpayin-redis: `parking_pre_notify:{lot_id}:{plate}` 저장 (TTL 1시간)
- pms-redis: `pre_reg:{lot_id}:{plate}` 저장 (PMS가 직접 처리, TTL 1시간)

DB 변경:

- 없음

외부 호출:

- PMS `POST /parking/pre-register`

실패 케이스:

- 인증 실패 (토큰 없음 또는 유효하지 않음) → 401
- 차량 없음 → 400
- 차량번호 미등록 → 400
- active billing key 없음 → 400
- PMS 사전 등록 실패 → 400

먼저 작성할 테스트:

- active billing key가 있으면 Redis에 pre-notify를 저장하고 PMS를 호출한다.
- billing key가 없으면 400을 반환하고 PMS를 호출하지 않는다.
- 차량번호가 없으면 400을 반환한다.
- PMS 사전 등록에 실패한 경우 400을 반환한다.

## UC-PARK-002. PMS 입차 webhook 처리

API:

- `POST /webhook/entry`

입력:

- Header `X-Webhook-Timestamp`
- Header `X-Webhook-Signature`
- `pms_session_id`
- `lot_id`
- `plate`
- `entry_time`

출력:

- 등록 차량이면 `status=confirmed`, `session_id`
- 미등록 차량이면 `status=not_registered`

사전 조건:

- 요청이 신뢰 가능한 PMS에서 온 것이어야 한다.
- timestamp는 백엔드 기준 5분 허용 오차 안에 있어야 한다.

처리:

- raw request body의 SHA-256 hash를 계산한다.
- `HMAC-SHA256(PMS_WEBHOOK_SECRET, "{timestamp}.{sha256(raw_body)}")`를 계산해 `X-Webhook-Signature`와 비교한다.
- `parking_pre_notify:{lot_id}:{plate}`를 조회한다.
- 없으면 세션을 만들지 않고 `not_registered`를 반환한다.
- 있으면 `car_id`를 가져온다.
- 해당 car_id에 active parking session이 이미 있는지 확인한다.
- 없으면 DB `parking_sessions`에 active 세션을 생성한다.
- Redis pre-notify를 삭제하거나 complete 처리한다.
- 앱 알림용 message를 발행한다.

Redis 변경:

- `parking_pre_notify:{lot_id}:{plate}` 삭제 또는 complete 처리

DB 변경:

- `parking_sessions` insert

외부 호출:

- MQTT 또는 AWS IoT publish

실패 케이스:

- PMS signature 불일치 또는 timestamp 만료
- 동일 car_id의 active session 중복
- pms_session_id 중복
- entry_time 형식 오류

먼저 작성할 테스트:

- PMS signature가 실패하면 401을 반환한다.
- pre-notify가 있으면 active parking session을 만든다.
- pre-notify가 없으면 세션을 만들지 않고 not_registered를 반환한다.
- 같은 pms_session_id webhook이 중복되어도 세션이 중복 생성되지 않는다.
- 같은 car_id에 active session이 있으면 기존 결과를 반환하거나 충돌을 처리한다.
- entry 타임 형식이 잘못되면 400을 반환한다

