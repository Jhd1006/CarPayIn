# 04. Entry / Parking Session Use Cases

## UC-PARK-001. 사전 입차 알림 등록

API:

- `POST /pre-notify`

입력:

- Bearer app access token
- `car_id`
- `lot_id`
- `plate`

출력:

- `status=registered`
- `car_id`
- `lot_id`
- `plate`

사전 조건:

- app access token이 유효해야 한다.
- 요청 `car_id`가 access token에 연결된 차량과 같아야 한다.
- 요청 `car_id`의 차량이 DB `vehicles`에 존재해야 한다.
- 차량번호가 등록되어 있어야 한다.
- `vehicle_billing_keys`에 active billing key가 있어야 한다.

처리:

- token에서 `user_id`, `car_id`를 확인한다.
- 요청 `car_id`와 token의 `car_id`가 같은지 검증한다.
- DB에서 차량과 차량번호를 조회한다.
- 요청 `plate`를 정규화하고 DB의 차량번호와 일치하는지 확인한다.
- active billing key 존재 여부를 확인한다.
- Redis `parking_pre_notify:{lot_id}:{plate}`를 incoming 상태로 저장한다.
- PMS에 차량번호 사전 등록을 요청한다.

Redis 변경:

- `parking_pre_notify:{lot_id}:{plate}` 저장

DB 변경:

- 없음

외부 호출:

- PMS `POST /parking/pre-register`

실패 케이스:

- 인증 실패
- 요청 차량과 token 차량 불일치
- 차량 없음
- 차량번호 없음
- 요청 차량번호와 등록 차량번호 불일치
- active billing key 없음
- PMS 사전 등록 실패

먼저 작성할 테스트:

- active billing key가 있으면 Redis에 pre-notify를 저장하고 PMS를 호출한다.
- billing key가 없으면 400을 반환하고 PMS를 호출하지 않는다.
- 차량번호가 없으면 400을 반환한다.
- token의 car_id와 요청 car_id가 다르면 403을 반환한다.
- PMS 사전 등록에 실패한 경우 400을 반환한다.

## UC-PARK-002. PMS 입차 webhook 처리

API:

- `POST /webhook/entry`

입력:

- `pms_session_id`
- `lot_id`
- `plate`
- `entry_time`

출력:

- 등록 차량이면 `status=confirmed`, `session_id`
- 미등록 차량이면 `status=not_registered`

사전 조건:

- 요청이 신뢰 가능한 PMS에서 온 것이어야 한다.

처리:

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

- PMS 인증 실패
- 동일 car_id의 active session 중복
- pms_session_id 중복
- entry_time 형식 오류

먼저 작성할 테스트:

- PMS 인증이 실패하면 401을 반환한다.
- pre-notify가 있으면 active parking session을 만든다.
- pre-notify가 없으면 세션을 만들지 않고 not_registered를 반환한다.
- 같은 pms_session_id webhook이 중복되어도 세션이 중복 생성되지 않는다.
- 같은 car_id에 active session이 있으면 기존 결과를 반환하거나 충돌을 처리한다.
- entry 타임 형식이 잘못되면 400을 반환한다

