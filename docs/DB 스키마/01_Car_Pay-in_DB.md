# Car Pay-in DB 스키마

## 개요

Car Pay-in DB는 AAOS 차량 결제 서비스에서 사용하는 서비스 DB이다.
현대 로그인 사용자, 사용자 차량, 차량별 빌링키, 주차 세션, 결제 이력, 앱/현대 인증 토큰 정보를 관리한다.

실제 카드 정보는 저장하지 않으며, 차량과 결제수단의 연결은 PG에서 발급한 `billing_key`를 기준으로 관리한다.

차량은 결제 주체이며, 하나의 차량은 현재 사용할 빌링키를 1개만 가진다.

## 자료형 기준

- 현대 API, PG, PMS 등 외부 시스템에서 받는 문자열은 `TEXT`를 사용한다.
- Car Pay-in 서비스가 직접 발급하는 내부 ID는 `UUID`를 사용한다.
- 업무적으로 길이가 명확한 값은 `VARCHAR(n)` 또는 `CHAR(n)`를 사용한다.
- 시간 값은 `TIMESTAMPTZ`를 사용한다.
- 상태값은 `TEXT`와 `CHECK` 제약으로 관리한다.

## users

현대 로그인 기준 사용자 정보를 저장한다.
사용자 식별자인 `user_id`, 이름, 생성 시각을 관리한다.

```sql
CREATE TABLE users (
  user_id TEXT PRIMARY KEY,
  name TEXT DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## vehicles

사용자에게 등록된 차량 정보를 저장한다.
차량 식별자인 `car_id`, 사용자 ID, 차량명, 차량번호, 등록 시각을 관리한다.

카드 정보나 빌링키는 이 테이블에 저장하지 않는다.

```sql
CREATE TABLE vehicles (
  car_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  car_sellname TEXT NOT NULL DEFAULT '',
  plate VARCHAR(20) NOT NULL DEFAULT '',
  registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_vehicles_user_id
ON vehicles(user_id);

CREATE UNIQUE INDEX idx_vehicles_plate
ON vehicles(plate)
WHERE plate <> '';
```

필드 기준:

- `car_id`: 현대 API에서 받은 차량 ID이므로 `TEXT`
- `user_id`: `users.user_id`와 같은 타입인 `TEXT`
- `car_sellname`: 현대 API에서 받은 차량명 또는 모델명이므로 `TEXT`
- `plate`: 차량번호는 업무적으로 짧고 명확하므로 `VARCHAR(20)`
- `registered_at`: 등록 시각이므로 `TIMESTAMPTZ`

## vehicle_billing_keys

차량과 PG 빌링키의 현재 매핑 정보를 저장한다.
`car_id`를 기본키로 사용하므로 차량 1대는 빌링키 1개만 가질 수 있다.

카드 변경 시 기존 row를 수정하여 새로운 `billing_key`로 교체한다.
차량별 현재 결제수단의 source of truth 역할을 한다.

```sql
CREATE TABLE vehicle_billing_keys (
  car_id TEXT PRIMARY KEY,
  billing_key TEXT UNIQUE NOT NULL,
  card_last_four CHAR(4) NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ,
  FOREIGN KEY (car_id) REFERENCES vehicles(car_id),
  CHECK (status IN ('active', 'inactive')),
  CHECK (card_last_four ~ '^[0-9]{4}$')
);
```

필드 기준:

- `car_id`: `vehicles.car_id`와 같은 타입인 `TEXT`
- `billing_key`: PG에서 발급하는 외부 값이므로 `TEXT`
- `card_last_four`: 카드 뒤 4자리이므로 `CHAR(4)`
- `status`: `CHECK`로 값 제한
- `created_at`, `updated_at`: `TIMESTAMPTZ`

## parking_sessions

차량의 주차 세션 정보를 저장한다.
Car Pay-in 기준 주차 세션 ID, PMS 기준 주차 세션 ID, 차량 ID, 주차장 ID, 차량번호, 입차/출차 시간, 세션 상태를 관리한다.

동일 차량은 active 주차 세션을 1개만 가질 수 있다.
PMS DB와는 분리되어 있으므로 `pms_session_id`는 물리 FK가 아니라 logical reference로 관리한다.

```sql
CREATE TABLE parking_sessions (
  session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pms_session_id TEXT,
  car_id TEXT NOT NULL,
  lot_id TEXT NOT NULL,
  plate VARCHAR(20) NOT NULL,
  entry_time TIMESTAMPTZ NOT NULL,
  exit_time TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ,
  FOREIGN KEY (car_id) REFERENCES vehicles(car_id),
  CHECK (status IN ('active', 'completed', 'cancelled'))
);

CREATE INDEX idx_parking_sessions_car_id
ON parking_sessions(car_id);

CREATE INDEX idx_parking_sessions_status
ON parking_sessions(status);

CREATE INDEX idx_parking_sessions_pms_session_id
ON parking_sessions(pms_session_id);

CREATE UNIQUE INDEX uniq_active_session_per_car
ON parking_sessions(car_id)
WHERE status = 'active';

CREATE UNIQUE INDEX uniq_parking_sessions_lot_pms
ON parking_sessions(lot_id, pms_session_id)
WHERE pms_session_id IS NOT NULL;
```

필드 기준:

- `session_id`: Car Pay-in 서비스가 만드는 주차 세션 ID이므로 `UUID`
- `pms_session_id`: PMS가 외부 API에 노출하는 주차 세션 ID이므로 `TEXT`
- `car_id`: 현대 차량 ID이므로 `TEXT`
- `lot_id`: PMS 또는 주차장 시스템의 외부 ID이므로 `TEXT`
- `plate`: 차량번호이므로 `VARCHAR(20)`
- `entry_time`, `exit_time`: 입차/출차 시각이므로 `TIMESTAMPTZ`
- `status`: `CHECK`로 값 제한
- `created_at`, `updated_at`: `TIMESTAMPTZ`

## transactions

Car Pay-in 기준 결제 이력을 저장한다.
출차 결제 요청 시 `pending` 상태로 생성되고, PG 결제 결과에 따라 `success`, `failed`, `cancelled`로 확정된다.

`car_id`는 결제 주체인 차량을 나타내고, `billing_key`는 해당 결제 시점에 사용한 PG 빌링키 스냅샷이다.
`pg_tx_id`를 통해 Mock PG DB의 거래 이력과 논리적으로 연결할 수 있다.

```sql
CREATE TABLE transactions (
  tx_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL,
  car_id TEXT NOT NULL,
  billing_key TEXT NOT NULL,
  pg_tx_id TEXT,
  amount INTEGER NOT NULL,
  currency CHAR(3) NOT NULL DEFAULT 'KRW',
  status TEXT NOT NULL DEFAULT 'pending',
  approval_no TEXT,
  idempotency_key TEXT NOT NULL,
  failed_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ,
  FOREIGN KEY (session_id) REFERENCES parking_sessions(session_id),
  FOREIGN KEY (car_id) REFERENCES vehicles(car_id),
  UNIQUE (idempotency_key),
  CHECK (amount > 0),
  CHECK (currency ~ '^[A-Z]{3}$'),
  CHECK (status IN ('pending', 'success', 'failed', 'cancelled'))
);

CREATE INDEX idx_transactions_session_id
ON transactions(session_id);

CREATE INDEX idx_transactions_car_id
ON transactions(car_id);

CREATE INDEX idx_transactions_billing_key
ON transactions(billing_key);

CREATE INDEX idx_transactions_pg_tx_id
ON transactions(pg_tx_id);
```

필드 기준:

- `tx_id`: Car Pay-in 서비스의 결제 이력 ID이므로 `UUID`
- `session_id`: `parking_sessions.session_id`와 같은 `UUID`
- `car_id`: 현대 차량 ID이므로 `TEXT`
- `billing_key`: PG에서 받은 외부 키의 스냅샷이므로 `TEXT`
- `pg_tx_id`: PG가 만든 거래 ID이므로 `TEXT`
- `amount`: KRW 원 단위 정수이므로 `INTEGER`
- `currency`: ISO 통화 코드이므로 `CHAR(3)`
- `status`: `CHECK`로 값 제한
- `approval_no`: PG 승인번호이므로 `TEXT`
- `idempotency_key`: 중복 결제 방지 키이므로 `TEXT`
- `failed_reason`: 실패 사유이므로 `TEXT`
- `created_at`, `updated_at`: `TIMESTAMPTZ`

## app_refresh_tokens

AAOS 앱 refresh token 정보를 저장한다.
refresh token 원문은 저장하지 않고 hash 값만 저장한다.

토큰은 수정되는 값이라기보다 발급/폐기 이력에 가까우므로 `updated_at` 없이 `revoked_at`으로 폐기 시점을 관리한다.

```sql
CREATE TABLE app_refresh_tokens (
  refresh_token_hash CHAR(64) PRIMARY KEY,
  user_id TEXT NOT NULL,
  car_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  FOREIGN KEY (user_id) REFERENCES users(user_id),
  FOREIGN KEY (car_id) REFERENCES vehicles(car_id),
  CHECK (status IN ('active', 'revoked', 'expired')),
  CHECK (refresh_token_hash ~ '^[a-f0-9]{64}$')
);

CREATE INDEX idx_app_refresh_tokens_user_id
ON app_refresh_tokens(user_id);

CREATE INDEX idx_app_refresh_tokens_car_id
ON app_refresh_tokens(car_id);

CREATE INDEX idx_app_refresh_tokens_expires_at
ON app_refresh_tokens(expires_at);
```

필드 기준:

- `refresh_token_hash`: SHA-256 hex 문자열이면 `CHAR(64)`
- `user_id`: 현대 사용자 ID이므로 `TEXT`
- `car_id`: 현대 차량 ID이므로 `TEXT`
- `status`: `CHECK`로 값 제한
- `created_at`, `expires_at`, `revoked_at`: `TIMESTAMPTZ`

## hyundai_tokens

현대 API refresh token을 저장한다.
현대 refresh token은 암호화해서 DB에 저장하고, 현대 access token은 DB에 저장하지 않고 Redis에만 캐시한다.

```sql
CREATE TABLE hyundai_tokens (
  user_id TEXT PRIMARY KEY,
  hyundai_refresh_token_encrypted TEXT NOT NULL,
  refresh_expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ,
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);
```

필드 기준:

- `user_id`: `users.user_id`와 같은 현대 사용자 ID이므로 `TEXT`
- `hyundai_refresh_token_encrypted`: 암호화된 토큰 문자열이므로 `TEXT`
- `refresh_expires_at`: 현대 refresh token 만료 시각이므로 `TIMESTAMPTZ`
- `created_at`, `updated_at`: `TIMESTAMPTZ`

## 최종 정리

Car Pay-in DB는 서비스 운영에 필요한 사용자, 차량, 빌링키, 주차 세션, 결제 이력, 인증 토큰을 관리하는 핵심 DB이다.

카드 원본 정보는 저장하지 않고 PG에서 발급한 `billing_key`만 관리한다.
차량은 결제 주체이며, `vehicle_billing_keys`에서 차량별 현재 빌링키를 관리한다.

카드 변경 이력은 별도로 저장하지 않고, 차량의 빌링키가 변경되면 기존 row를 업데이트한다.
다만 결제 당시 사용한 `billing_key`는 `transactions`에 스냅샷으로 저장하므로, 과거 결제가 어떤 빌링키로 처리되었는지는 결제 이력에서 확인할 수 있다.

동일 차량의 active 주차 세션은 1개만 허용하고, 결제 요청은 `pending` 상태로 생성한 뒤 PG 결과에 따라 최종 상태를 확정한다.
