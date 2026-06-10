# 04. 입차 사전알림 / 주차 세션 생성

관련 다이어그램: `docs/diagrams/04-entry-parking-session.mmd`

## 이 단계의 목적

차량이 주차장에 들어가기 전에 PMS에 번호판을 미리 알려두고, 실제 입차가 발생하면 Car Pay-in 기준 주차 세션을 생성하는 단계다.

입차 시에는 결제를 하지 않는다. 이 단계의 핵심은 "이 차량이 Car Pay-in 자동결제 대상 차량으로 입차했다"는 세션을 만드는 것이다.

## 등장하는 참여자

- AAOS App: 앱 내 제휴 주차장 목록에서 원하는 주차장의 길안내 버튼을 눌러 사전알림을 보낸다.
- Car Pay-in Backend: 차량과 billing key를 검증하고 사전알림 상태를 저장한다.
- carpayin-redis: `parking_pre_notify:{lot_id}:{plate}` 사전알림 상태를 임시 저장한다.
- Car Pay-in DB: Car Pay-in 기준 주차 세션을 저장한다.
- Parking PMS: 주차장 현장 시스템 역할을 하며 번호판 사전 등록과 LPR 이벤트를 처리한다.
- pms-redis: `pre_reg:{lot_id}:{plate}` 사전등록 차량번호를 임시 저장한다.
- PMS DB: PMS 기준 입차 세션 정보를 저장한다.
- LPR Camera: 입구에서 번호판을 인식한다.

## 핵심 개념

**사전알림은 두 Redis에 각각 다른 용도로 저장된다.**

- `carpayin-redis`의 `parking_pre_notify:{lot_id}:{plate}`: "이 번호판 차량이 곧 이 주차장에 들어올 예정이고, Car Pay-in에 등록된 차량이다"는 상태. `car_id`, `user_id`를 포함해서 나중에 PMS webhook을 받았을 때 세션 생성에 사용한다.
- `pms-redis`의 `pre_reg:{lot_id}:{plate}`: PMS에서 LPR 입차 시 해당 번호판이 Car Pay-in 사전 등록 차량인지 판별하는 데만 사용한다. 값은 `"1"`로 단순하게 관리하고 TTL 1시간 후 자동 만료된다.

PMS DB의 주차 세션과 Car Pay-in DB의 주차 세션은 서로 다른 시스템의 데이터다. 두 시스템은 `pms_session_id`, `lot_id`, `plate` 같은 값으로 논리적으로 연결된다.

## 단계별 흐름

**사전알림 등록 (길안내 버튼 탭)**

1. 사용자가 앱에서 `GET /parking/lots`로 조회한 제휴 주차장 목록을 본다.
2. 원하는 주차장의 길안내 버튼을 탭한다.
3. 앱은 `POST /parking/navigate`로 `lot_id`만 백엔드에 보낸다. `car_id`와 `plate`는 보내지 않는다.
4. 백엔드는 Authorization 헤더의 access token에서 `car_id`와 `user_id`를 추출한다.
5. 백엔드는 `vehicles`에서 해당 `car_id`의 차량과 번호판(`plate`)을 조회한다. 차량이 없거나 번호판이 등록 안 되어 있으면 400 반환.
6. 백엔드는 `vehicle_billing_keys`에서 active billing key가 있는지 확인한다. 없으면 400 반환.
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

**입차 처리 (LPR 인식)**

10. 실제 차량이 입구에 도착하면 LPR Camera가 번호판을 인식한다.
11. PMS는 번호판 인식 즉시 입구 차단기를 연다. Car Pay-in 사용자인지와 무관하게 모든 차량에 동일하게 적용한다.
12. PMS는 PMS DB에 PMS 기준 `parking_sessions`를 생성한다 (`status=active`). 모든 차량에 대해 생성한다.
13. PMS는 pms-redis에서 `pre_reg:{lot_id}:{plate}` 키를 조회한다.
14. 키가 존재하면 Car Pay-in 사전 등록 차량이므로 키를 삭제(consume)한다. 키가 없으면 webhook을 보내지 않는다.
15. PMS는 입차 이벤트 raw body를 만들고 `PMS_WEBHOOK_SECRET`으로 `X-Webhook-Timestamp`, `X-Webhook-Signature`를 생성한다.
16. PMS는 Car Pay-in Backend에 `POST /webhook/entry`로 입차 이벤트를 보낸다.
17. 백엔드는 같은 raw body와 timestamp로 HMAC을 다시 계산해 신뢰할 수 있는 PMS 요청인지 확인한다.
18. 백엔드는 carpayin-redis의 `parking_pre_notify:{lot_id}:{plate}`를 조회해 `car_id`를 가져온다.
19. 백엔드는 Car Pay-in DB의 `parking_sessions`에 서비스 기준 주차 세션을 생성한다.
20. 백엔드는 사용이 끝난 `parking_pre_notify:{lot_id}:{plate}`를 삭제한다.
21. 백엔드는 MQTT로 앱에 입차 알림을 전송한다.
19. 앱은 입차 알림을 받고 로컬 상태를 `parked=true`로 저장한다.

## 이 단계가 끝나면 남는 데이터

carpayin-redis:

- `parking_pre_notify:{lot_id}:{plate}`: 입차 webhook 처리 후 삭제된다.

pms-redis:

- `pre_reg:{lot_id}:{plate}`: LPR 입차 시 consume 후 삭제된다. 1시간 TTL로 자동 만료된다.

Car Pay-in DB:

- `parking_sessions`: Car Pay-in 기준 active 주차 세션

PMS DB:

- `parking_sessions`: PMS 기준 주차 세션 (`status=active`)

앱 로컬 저장소:

- `parked=true`
- `session_id`
- `lot_id`

## 발표 멘트

네 번째 단계는 입차 사전알림과 주차 세션 생성입니다. 사용자가 앱에서 제휴 주차장 목록을 보고 길안내 버튼을 누르면, 앱은 주차장 ID 하나만 백엔드에 보냅니다. 백엔드는 토큰에서 차량 정보를 꺼내 차량과 빌링키를 검증한 뒤 두 Redis에 사전 등록 정보를 저장합니다. 이후 실제 차량이 입구에 들어오면 LPR이 번호판을 인식하고, PMS는 모든 차량에 즉시 차단기를 열고 세션을 생성합니다. Car Pay-in 사전 등록 차량이면 백엔드에 webhook을 보내 앱 알림까지 이어집니다.
