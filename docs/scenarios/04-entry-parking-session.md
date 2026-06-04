# 04. 입차 사전알림 / 주차 세션 생성

관련 다이어그램: `docs/diagrams/04-entry-parking-session.mmd`

## 이 단계의 목적

차량이 주차장에 들어가기 전에 PMS에 번호판을 미리 알려두고, 실제 입차가 발생하면 Car Pay-in 기준 주차 세션을 생성하는 단계다.

입차 시에는 결제를 하지 않는다. 이 단계의 핵심은 "이 차량이 Car Pay-in 자동결제 대상 차량으로 입차했다"는 세션을 만드는 것이다.

## 등장하는 참여자

- AAOS App: 지오펜스 진입 또는 내비 목적지 설정을 감지하고 사전알림을 보낸다.
- Car Pay-in Backend: 차량과 billing key를 검증하고 사전알림 상태를 저장한다.
- Redis: 주차장/번호판 기준 사전알림 상태를 임시 저장한다.
- Car Pay-in DB: Car Pay-in 기준 주차 세션을 저장한다.
- Parking PMS: 주차장 현장 시스템 역할을 하며 번호판 사전 등록과 LPR 이벤트를 처리한다.
- PMS DB: PMS 기준 입차 세션과 상태를 저장한다.
- LPR Camera: 입구에서 번호판을 인식한다.

## 핵심 개념

`parking_pre_notify:{lot_id}:{plate}`는 "이 번호판 차량이 곧 이 주차장에 들어올 예정이고, Car Pay-in에 등록된 차량이다"라는 임시 상태다.

PMS DB의 주차 세션과 Car Pay-in DB의 주차 세션은 서로 다른 시스템의 데이터다. 두 시스템은 `pms_session_id`, `lot_id`, `plate` 같은 값으로 논리적으로 연결된다.

## 단계별 흐름

1. 앱은 차량이 특정 주차장에 접근했거나 목적지로 설정된 것을 감지한다.
2. 앱은 `/pre-notify`로 `car_id`, `lot_id`, `plate`를 백엔드에 보낸다.
3. 백엔드는 요청한 `car_id`가 access token에 연결된 차량과 같은지 확인한다.
4. 백엔드는 `vehicles`에서 차량이 등록되어 있는지 확인한다.
5. 백엔드는 `vehicle_billing_keys`에서 active billing key가 있는지 확인한다.
6. 검증이 통과하면 Redis에 `parking_pre_notify:{lot_id}:{plate}`를 저장한다.

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

7. 백엔드는 PMS에 번호판 사전 등록 요청을 보낸다.
8. PMS는 PMS DB의 `pre_registrations`에 사전 등록 정보를 저장한다.
9. 실제 차량이 입구에 도착하면 LPR Camera가 번호판을 인식한다.
10. PMS는 해당 번호판이 사전 등록된 차량인지 확인한다.
11. PMS는 PMS DB에 PMS 기준 `parking_sessions`를 생성하고 `pre_registrations` 상태를 `consumed`로 바꾼다.
12. PMS는 Car Pay-in Backend에 `/webhook/entry`로 입차 이벤트를 보낸다.
13. 백엔드는 Redis의 `parking_pre_notify:{lot_id}:{plate}`를 조회한다.
14. 조회에 성공하면 백엔드는 Car Pay-in DB의 `parking_sessions`에 서비스 기준 주차 세션을 생성한다.
15. 백엔드는 사용이 끝난 `parking_pre_notify:{lot_id}:{plate}`를 삭제한다.
16. 앱은 입차 알림을 받고 로컬 상태를 `parked=true`로 저장한다.

## 이 단계가 끝나면 남는 데이터

Redis:

- `parking_pre_notify:{lot_id}:{plate}`: 입차 확인 후 삭제된다.

Car Pay-in DB:

- `parking_sessions`: Car Pay-in 기준 active 주차 세션

PMS DB:

- `pre_registrations`: 처리 완료된 번호판 사전 등록 이력 (`status=consumed`)
- `parking_sessions`: PMS 기준 주차 세션

앱 로컬 저장소:

- `parked=true`
- `session_id`
- `lot_id`

## 발표 멘트

네 번째 단계는 입차 사전알림과 주차 세션 생성입니다. 앱이 주차장 접근을 감지하면 백엔드는 차량이 등록되어 있고 active billing key가 있는지 확인합니다. 이후 Redis에 사전알림 상태를 저장하고 PMS에 번호판을 미리 등록합니다. 실제 입구 LPR이 번호판을 인식하면 PMS는 자기 DB에 세션을 만들고 백엔드에 입차 웹훅을 보냅니다. 백엔드는 Redis의 사전알림을 확인한 뒤 Car Pay-in DB에 주차 세션을 생성합니다.
