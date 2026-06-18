# Redis Key 설계

## 개요

Redis는 서비스별로 분리된 두 인스턴스로 운영한다.

- **carpayin-redis** (port 6379): Car Pay-in Backend 전용. QR 로그인/OAuth 진행 상태, OAuth state 매핑, 현대 로그인 직후 임시 데이터, 앱 로그인 결과, 카드 등록 웹뷰 상태, 사전 입차 등록 상태, 요금 quote를 TTL 기반으로 관리한다.
- **pms-redis** (port 6380): PMS 전용. Car Pay-in 사전등록 차량번호(`pre_reg:{lot_id}:{plate}`)를 TTL 기반으로 관리한다.

DB에는 장기 보관이 필요한 데이터만 저장하고, Redis에는 짧은 시간 동안만 필요한 세션성 데이터를 저장한다.

## qr_session:{session_id}

QR/OAuth state 검증용 세션 정보를 저장한다.
AAOS 앱에서 QR 로그인을 시작하면 생성되며, OAuth 완료 전까지 세션 상태를 확인하는 데 사용한다.

TTL은 15분이다.

```json
{
  "vin_hash": "...",
  "status": "pending",
  "created_at": "...",
  "expires_at": "...",
  "debug_message": ""
}
```

필드 설명:

- `vin_hash`: 차량 VIN을 hash한 값
- `status`: QR/OAuth 세션 상태, `pending`, `complete`, `expired`, `failed`
- `created_at`: 세션 생성 시각
- `expires_at`: 세션 만료 시각
- `debug_message`: Mock 또는 개발 환경에서 확인할 디버그 메시지

## oauth_state:{oauth_state}

현대 OAuth 요청에 사용하는 난수 `state`와 실제 QR 로그인 `session_id`를 매핑한다.
OAuth `state`에 `session_id`를 직접 넣지 않기 위해 사용한다.

TTL은 15분이다.
callback 처리 후에는 재사용되지 않도록 삭제하거나 `used` 상태로 변경한다.

```json
{
  "session_id": "...",
  "status": "pending",
  "created_at": "...",
  "expires_at": "..."
}
```

필드 설명:

- `session_id`: 실제 QR 로그인 세션 ID
- `status`: OAuth state 상태, `pending`, `used`, `expired`
- `created_at`: state 생성 시각
- `expires_at`: state 만료 시각

## hyundai_oauth:{session_id}

현대 로그인 직후, 차량 확정 전까지 임시 결과를 저장한다.
사용자 정보, 차량 목록, confirm-car 호출에 사용할 임시 access token을 보관한다.

현대 access token과 refresh token은 OAuth callback 시 동기로 사용 후 즉시 버린다. 별도로 저장하지 않는다.

TTL은 15분이다.

```json
{
  "user_id": "...",
  "name": "...",
  "temp_access_token": "...",
  "cars": [
    {
      "car_id": "...",
      "car_sellname": "...",
      "plate": "..."
    }
  ],
  "created_at": "...",
  "expires_at": "..."
}
```

필드 설명:

- `user_id`: 현대 로그인 기준 사용자 ID
- `name`: 사용자 이름
- `temp_access_token`: confirm-car API 호출에 사용할 임시 access token
- `cars`: 현대 API에서 조회한 차량 목록
- `created_at`: 저장 시각
- `expires_at`: 만료 시각

## app_login_result:{session_id}

AAOS 앱이 polling으로 로그인 완료 여부를 확인할 때 사용하는 결과 데이터를 저장한다.
현대 로그인과 차량 목록 조회가 완료되면 차량 확정용 임시 access token, 사용자 정보, 차량 목록을 저장한다.
최종 앱 access/refresh token은 차량 확정 API(`/auth/confirm-car`) 응답으로 발급하고, refresh token hash는 DB `app_refresh_tokens`에 저장한다.

TTL은 5분이다.

```json
{
  "status": "complete",
  "temp_access_token": "...",
  "user_id": "...",
  "name": "...",
  "cars": [
    {
      "car_id": "...",
      "car_sellname": "...",
      "plate": "..."
    }
  ]
}
```

필드 설명:

- `status`: 앱 로그인 처리 상태, `complete`, `failed`
- `temp_access_token`: 차량 확정 API 호출에 사용할 임시 access token
- `user_id`: 로그인 완료된 사용자 ID
- `name`: 로그인 완료된 사용자 이름
- `cars`: 사용자가 선택할 수 있는 현대 차량 목록

## mock_pg_card_register:{order_id}

카드 등록 웹뷰의 order 상태를 저장한다.
Car Pay-in이 Mock PG 카드 등록 웹뷰를 열기 전에 생성하고, PG 웹훅 또는 리다이렉트 검증에 사용한다.

TTL은 30분이다.
웹훅 성공 후 삭제한다.

웹훅 중복 처리는 Mock PG DB `billing_keys.order_id` UNIQUE, Car Pay-in DB `vehicle_billing_keys.car_id` PRIMARY KEY 기준으로 idempotent하게 처리한다.

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

필드 설명:

- `order_id`: 카드 등록 요청 ID, Mock PG `billing_keys.order_id`와 연결
- `user_id`: 카드 등록을 요청한 사용자 ID
- `car_id`: 빌링키를 연결할 차량 ID
- `status`: 카드 등록 상태, `pending`, `complete`, `expired`, `failed`
- `created_at`: 카드 등록 세션 생성 시각
- `expires_at`: 카드 등록 세션 만료 시각

## parking_pre_notify:{lot_id}:{plate}

사전 입차 알림 상태를 저장한다.
AAOS 앱이 인증된 상태에서 차량, 차량번호, active 빌링키 검증을 마친 뒤 PMS에 차량번호를 사전 등록할 때 생성한다.
PMS 입차 webhook 수신 시 해당 차량이 사전 등록된 Car Pay-in 차량인지 확인하는 데 사용한다.

TTL은 1시간이다.
입차 webhook 처리 완료 후 삭제하거나 완료 상태로 변경한다.

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

필드 설명:

- `user_id`: 사전 입차 알림을 요청한 현대 사용자 ID
- `car_id`: 결제 주체 차량 ID
- `lot_id`: 입차 예정 주차장 ID
- `plate`: PMS에 사전 등록한 차량번호
- `status`: 사전 입차 상태, `incoming`, `complete`, `expired`, `failed`
- `created_at`: 사전 입차 등록 시각
- `expires_at`: 사전 입차 등록 만료 시각

## parking_fee_quote:{session_id}

요금 조회 시 PMS가 반환한 금액을 짧게 고정한다.
결제 요청 시 PMS에 금액을 다시 조회하지 않고, 앱이 전달한 `amount`, `currency`가 직전 요금 조회 결과와 일치하는지 검증하는 데 사용한다.

TTL은 15분이다.
quote가 만료되면 앱은 요금을 다시 조회해야 한다.

```json
{
  "session_id": "...",
  "lot_id": "...",
  "amount": 6000,
  "duration": 30,
  "currency": "KRW",
  "entry_time": "...",
  "status": "active",
  "created_at": "...",
  "expires_at": "..."
}
```

필드 설명:

- `session_id`: Car Pay-in 기준 주차 세션 ID
- `lot_id`: 주차장 ID
- `amount`: PMS가 계산한 현재 결제 금액
- `duration`: 주차 시간 (분)
- `currency`: 결제 통화
- `entry_time`: 입차 시각
- `status`: quote 상태, `active` 고정
- `created_at`: 요금 quote 생성 시각
- `expires_at`: 요금 quote 만료 시각

## entry_notify_retry:{session_id}

입차 확정 알림 MQTT 발행이 실패한 경우 재시도 대기 이벤트를 저장한다.
`NotifyRetryWorker`가 60초마다 SCAN으로 이 패턴의 키를 순회해 재시도하고, 성공 시 키를 삭제한다.

TTL은 1시간이다.

```json
{
  "car_id": "...",
  "session_id": "...",
  "lot_id": "...",
  "entry_time": "..."
}
```

필드 설명:

- `car_id`: MQTT 알림 대상 차량 ID
- `session_id`: Car Pay-in 기준 주차 세션 ID
- `lot_id`: 입차 주차장 ID
- `entry_time`: 입차 시각

## pms_payment_retry:{tx_id}

PMS 결제 완료 통보가 실패했지만 Car Pay-in 결제는 성공한 경우 재전송 대기 이벤트를 저장한다.
`NotifyRetryWorker`가 60초마다 SCAN으로 이 패턴의 키를 순회해 재시도하고, 성공 시 키를 삭제한다.

TTL은 7일이다.

```json
{
  "event_type": "pms_payment_notify",
  "tx_id": "...",
  "payload": {
    "pms_session_id": "...",
    "carpay_parking_session_id": "...",
    "carpay_tx_id": "...",
    "amount": 5000,
    "currency": "KRW",
    "approval_no": "...",
    "idempotency_key": "..."
  },
  "reason": "timeout",
  "status": "pending",
  "created_at": "...",
  "expires_at": "..."
}
```

---

## [PMS Redis] parking_session:{lot_id}:{plate}

주차 중인 차량의 실시간 상태를 저장한다.
LPR 입차 시 생성되고, 출차 LPR이 확인되면 삭제된다.
출차 판단(paid 여부 확인)은 DB가 아닌 이 키를 우선 조회한다. Redis 재시작 등으로 키가 유실된 경우에만 DB를 fallback으로 조회한다.

**Redis 인스턴스: pms-redis (port 6380)**

TTL은 72시간이다.

```json
{
  "pms_session_id": "pms-sess-abc123",
  "lot_id": "LOT_GN_01",
  "plate": "12가3456",
  "entry_time": "2026-06-18T10:00:00",
  "status": "active"
}
```

상태 전이:
- `active`: 입차 후 결제 전
- `paid`: Car Pay-in 결제 완료 통보 수신 후 → 출차 차단기 개방 대기

출차 LPR이 `paid` 상태를 확인하면 차단기를 개방하고 키를 삭제한다.
이후 해당 차량의 재입차는 새 키로 처리된다.

## [PMS Redis] pre_reg:{lot_id}:{plate}

Car Pay-in 앱에서 사전 입차 등록된 차량번호를 PMS Redis에 저장한다.
LPR 입차 이벤트 수신 시 해당 차량이 Car Pay-in 사전 등록 차량인지 확인하는 데 사용한다.
등록 확인 후 키를 삭제(consume)한다.

**Redis 인스턴스: pms-redis (port 6380)**

TTL은 1시간이다.

```
pre_reg:{lot_id}:{plate} → "1"
```

예시:

```
pre_reg:LOT_GN_01:12가3456 → "1"  (TTL: 3600)
```

필드 설명:

- `lot_id`: 입차 예정 주차장 ID
- `plate`: 사전 등록된 차량번호
- 값은 항상 `"1"` (존재 여부만 확인)

## 최종 정리

Redis는 두 인스턴스로 서비스를 분리 운영한다.

**carpayin-redis (port 6379)** — Car Pay-in Backend 전용:
QR 로그인, OAuth state 매핑, 현대 OAuth 임시 결과, AAOS 앱 로그인 polling, 카드 등록 웹뷰 상태, 사전 입차 등록 상태, 요금 quote, 알림 재시도 이벤트(`entry_notify_retry:*`, `pms_payment_retry:*`)처럼 짧은 시간 동안만 필요한 데이터를 TTL 기반으로 관리한다.

**pms-redis (port 6380)** — PMS 전용:
- `pre_reg:{lot_id}:{plate}`: Car Pay-in 사전 등록 차량 여부. LPR 입차 시 확인 후 삭제. TTL 1시간.
- `parking_session:{lot_id}:{plate}`: 주차 중인 차량의 실시간 상태(`active` / `paid`). 출차 판단 시 DB 대신 우선 조회. 출차 완료 시 삭제. TTL 72시간.

Redis = 실시간 상태판 (빠른 조회), DB = 영구 이력 (감사/정산용)으로 책임을 분리한다.

현대 access/refresh token은 OAuth callback에서 동기로 사용 후 즉시 버린다. Redis나 DB에 저장하지 않는다.
장기 보관이 필요한 사용자, 차량, 빌링키, 결제 이력, 앱 refresh token은 DB에 저장한다.

운영 환경에서는 Redis에 저장되는 app token 등 민감정보에 대해 TTL, ACL, 암호화, 접근 권한을 별도로 관리해야 한다.
