# Redis Key 설계

## 개요

Redis는 Car Pay-in 서비스에서 사용하는 임시 상태 저장소이다.
QR 로그인/OAuth 진행 상태, OAuth state 매핑, 현대 로그인 직후 임시 데이터, 앱 로그인 결과, 현대 access token 캐시, 카드 등록 웹뷰 상태, 사전 입차 등록 상태, 요금 quote를 TTL 기반으로 관리한다.

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

현대 로그인 직후, 차량 확정 전까지 임시 OAuth/Data API 결과를 저장한다.
사용자 정보, 현대 token, 현대 Data API에서 받은 차량 목록을 임시로 보관한다.

TTL은 15분이다.
운영 환경에서는 Redis ACL, 암호화, 민감정보 최소 저장 정책을 검토해야 한다.

```json
{
  "user_id": "...",
  "name": "...",
  "hyundai_access_token": "...",
  "hyundai_refresh_token": "...",
  "access_expires_at": "...",
  "refresh_expires_at": "...",
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

- `user_id`: 현대 로그인 기준 사용자 ID
- `name`: 사용자 이름
- `hyundai_access_token`: 현대 API 호출용 access token
- `hyundai_refresh_token`: 현대 API refresh token, 최종적으로 DB에 암호화 저장
- `access_expires_at`: 현대 access token 만료 시각
- `refresh_expires_at`: 현대 refresh token 만료 시각
- `cars`: 현대 API에서 조회한 차량 목록

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

## hyundai_access:{user_id}

현대 API 호출용 access token을 캐시한다.
현대 access token은 DB에 저장하지 않고 Redis에만 저장한다.

TTL은 현대 access token 만료 시각까지 설정한다.

```json
{
  "hyundai_access_token": "...",
  "access_expires_at": "..."
}
```

필드 설명:

- `hyundai_access_token`: 현대 API 호출용 access token
- `access_expires_at`: 현대 access token 만료 시각

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

TTL은 5분이다.
quote가 만료되면 앱은 요금을 다시 조회해야 한다.

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

필드 설명:

- `session_id`: Car Pay-in 기준 주차 세션 ID
- `pms_session_id`: PMS 기준 주차 세션 ID
- `car_id`: 결제 주체 차량 ID
- `lot_id`: 주차장 ID
- `plate`: 차량번호
- `amount`: PMS가 계산한 현재 결제 금액
- `currency`: 결제 통화
- `created_at`: 요금 quote 생성 시각
- `expires_at`: 요금 quote 만료 시각

## 최종 정리

Redis는 Car Pay-in 서비스의 단기 상태 저장소이다.
QR 로그인, OAuth state 매핑, 현대 OAuth, AAOS 앱 로그인 polling, 현대 access token 캐시, 카드 등록 웹뷰 상태, 사전 입차 등록 상태, 요금 quote처럼 짧은 시간 동안만 필요한 데이터를 TTL 기반으로 관리한다.

장기 보관이 필요한 사용자, 차량, 빌링키, 결제 이력, refresh token 정보는 DB에 저장한다.
현대 access token은 DB에 저장하지 않고 Redis에만 캐시한다.

운영 환경에서는 Redis에 저장되는 OAuth token, app token 등 민감정보에 대해 TTL, ACL, 암호화, 접근 권한을 별도로 관리해야 한다.
