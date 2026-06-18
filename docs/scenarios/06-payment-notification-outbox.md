# 06. 앱 알림 발송과 재시도

## 목적

Car Pay-in Backend는 입차 확정과 결제 완료 시점에 AAOS 앱에 알림을 보낸다.
알림 발송이 실패해도 결제·세션 처리 자체는 보존되고, 백그라운드 워커가 주기적으로 재시도한다.

## 참여 컴포넌트

- Car Pay-in Backend (`PaymentOutboxWorker`, `MqttNotificationPublisher`, `NotifyRetryWorker`)
- Car Pay-in DB (`payment_notification_outbox`)
- MQTT Broker (Eclipse Mosquitto)
- carpayin-redis (재시도 이벤트 저장)
- AAOS App (`MqttManager`)
- Parking PMS (결제 완료 통보 수신)

## 알림 채널

paho-mqtt 라이브러리로 Mosquitto 브로커에 직접 발행한다.

MQTT 토픽:

- 입차 확정: `parking/confirmed/{car_id}` (QoS 1)
- 결제 완료: `payment/complete/{car_id}` (QoS 1)

앱은 `isCleanSession=false` (persistent session)으로 연결한다. 앱이 오프라인 상태일 때 브로커가 QoS 1 메시지를 버퍼링하고, 재연결 시 전달한다.

## 흐름 — 입차 확정 알림

1. PMS 입차 webhook → `POST /webhook/entry` 처리 성공, `parking_sessions` 생성.
2. `notification_publisher.publish_entry_notification()` 호출.
   - 성공 → 앱이 `parking/confirmed/{car_id}` 수신 → `parked=true` 저장.
   - 실패 → `entry_notify_retry:{session_id}` Redis 키 저장 (TTL 1시간).
3. `NotifyRetryWorker`가 60초마다 `entry_notify_retry:*` 키를 SCAN해 재시도.
4. 재시도 성공 → 키 삭제.

```json
// parking/confirmed/{car_id} 페이로드
{
  "session_id": "...",
  "lot_id": "...",
  "entry_time": "..."
}
```

## 흐름 — 결제 완료 알림

1. PG 결제 성공 → 동일 DB transaction에서 `transactions` success 갱신과
   `payment_notification_outbox` pending 이벤트 생성을 함께 처리.
2. `PaymentOutboxWorker`가 5초마다 발행 가능한 이벤트를 claim한다.
3. SQS 또는 로컬 MQTT 발행에 성공하면 outbox 상태를 `published`로 변경한다.
   실패하면 `failed`로 변경하고 지수 백오프로 재시도하며, 최대 시도 횟수를
   넘으면 `dead`로 변경한다.
4. 앱이 `payment/complete/{car_id}` 수신 → `parked=false` 저장.
5. PMS `POST /payment/complete` 통보.
   - 성공 → PMS `parking_sessions` `paid` 전환, 출구 차단기 개방 가능.
   - 실패 → `pms_payment_retry:{tx_id}` Redis 키 저장 (TTL 7일).
6. `NotifyRetryWorker`가 60초마다 `pms_payment_retry:*` 키를 SCAN해 재시도.
7. 재시도 성공 → 키 삭제, PMS `paid` 전환.

```json
// payment/complete/{car_id} 페이로드
{
  "event_type": "payment.completed",
  "tx_id": "...",
  "session_id": "...",
  "car_id": "...",
  "lot_id": "...",
  "amount": 6000,
  "currency": "KRW",
  "approval_no": "..."
}
```

## NotifyRetryWorker

- 파일: `services/carpayin-backend/app/infra/workers/notify_retry_worker.py`
- FastAPI lifespan(`asynccontextmanager`)으로 앱 시작 시 daemon thread 기동.
- `interval_seconds=60` 기본값.
- Redis SCAN (`cursor=0` 기반 비블로킹 순회, `count=100`씩).
- 재시도 성공 시 해당 키 삭제 (멱등).
- 재시도 실패 시 키 유지, 다음 interval에 재시도.

## PaymentOutboxWorker

- 파일: `services/carpayin-backend/app/infra/workers/payment_outbox_worker.py`
- FastAPI lifespan으로 앱 시작 시 daemon thread 기동.
- `PAYMENT_OUTBOX_POLL_INTERVAL_SECONDS=5` 기본값.
- `SELECT ... FOR UPDATE SKIP LOCKED`로 여러 인스턴스가 같은 이벤트를 동시에
  claim하지 않도록 한다.
- claim 시 `publishing` 상태와 lease 만료 시각을 기록한다.
- 프로세스가 발행 도중 종료되면 lease 만료 후 다시 claim할 수 있다.
- 실패 시 최대 5분까지 증가하는 지수 백오프를 적용한다.

## 재시도 TTL 정책

| 알림 종류 | Redis 키 패턴 | TTL |
|---|---|---|
| 입차 확정 (MQTT) | `entry_notify_retry:{session_id}` | 1시간 |
| PMS 결제 통보 | `pms_payment_retry:{tx_id}` | 7일 |

PMS 통보 실패는 사용자가 결제를 마쳤는데 출구 차단기가 열리지 않는 직접적 불편을 유발하므로 TTL을 7일로 길게 잡는다.

## 이유

- 결제 성공(`transactions`)과 알림 발송을 분리한다. 알림 실패가 결제 롤백을 유발하지 않는다.
- Redis TTL 기반 재시도: 성공 후 자동 삭제되고 단기 재시도 용도에 적합하다.
