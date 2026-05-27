# PMS DB 스키마

## 개요

PMS DB는 Mock 주차장 시스템에서 사용하는 간소화된 DB이다.
입차 예정 차량의 사전등록, 차량 입차/출차 세션, Car Pay-in 결제 요청 이력을 관리한다.

주차장은 UI상 여러 개처럼 보일 수 있지만, 실제 시뮬레이션에서는 하나의 Mock 주차장으로 처리한다.
따라서 주차장 정보, 게이트 정보, 요금 정책은 DB에 저장하지 않고 서버 코드에서 하드코딩한다.

PMS는 카드 정보나 빌링키를 저장하지 않는다.
차량은 차량번호 `plate` 기준으로 식별하고, 결제가 필요한 시점에 Car Pay-in 서비스로 결제를 요청한다.

Car Pay-in DB와는 분리된 DB이므로 `carpay_parking_session_id`, `carpay_tx_id`는 물리 FK가 아니라 logical reference로 관리한다.

PostgreSQL에서 `gen_random_uuid()`를 사용하려면 `pgcrypto` 확장이 필요하다.

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

## pre_registrations

Car Pay-in Backend가 입차 전에 전달한 주차장/차량번호 등록 상태를 저장한다.
LPR 입차 이벤트는 `pre_registered` 상태인 차량만 처리하며, 입차 세션이 생성되면 상태를 `consumed`로 갱신한다.

```sql
CREATE TABLE pre_registrations (
  lot_id TEXT NOT NULL,
  plate VARCHAR(20) NOT NULL,
  status TEXT NOT NULL DEFAULT 'pre_registered',
  registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  consumed_at TIMESTAMPTZ,
  PRIMARY KEY (lot_id, plate),
  CHECK (status IN ('pre_registered', 'consumed', 'cancelled'))
);

CREATE INDEX idx_pms_pre_registrations_status
ON pre_registrations(status);
```

## parking_sessions

PMS 기준 주차 세션 정보를 저장한다.
차량번호, 입차/출차 시각, 주차 세션 상태를 관리한다.

동일 차량번호는 active 주차 세션을 1개만 가질 수 있다.

```sql
CREATE TABLE parking_sessions (
  pms_session_id TEXT PRIMARY KEY,
  lot_id TEXT NOT NULL DEFAULT 'mock_lot_001',
  plate VARCHAR(20) NOT NULL DEFAULT '',
  entry_time TIMESTAMPTZ NOT NULL,
  exit_time TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ,
  CHECK (status IN ('active', 'exited', 'cancelled'))
);

CREATE INDEX idx_pms_parking_sessions_plate
ON parking_sessions(plate);

CREATE INDEX idx_pms_parking_sessions_status
ON parking_sessions(status);

CREATE UNIQUE INDEX uniq_active_pms_session_per_plate
ON parking_sessions(plate)
WHERE status = 'active';
```

Logical reference:

```text
parking_sessions.pms_session_id
-> Car Pay-in 결제 요청 시 외부 요청의 기준 session id로 전달된다.
```

## payment_requests

PMS가 Car Pay-in에 요청한 출차 결제 이력을 저장한다.
PMS 주차 세션, 결제 금액, 요청 상태, Car Pay-in 응답 결과를 관리한다.

동일 결제 요청의 중복 처리를 막기 위해 `idempotency_key`를 unique로 관리한다.

```sql
CREATE TABLE payment_requests (
  payment_request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pms_session_id TEXT NOT NULL,
  carpay_parking_session_id TEXT,
  carpay_tx_id TEXT,
  amount INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'KRW',
  status TEXT NOT NULL DEFAULT 'pending',
  idempotency_key TEXT NOT NULL,
  approval_no TEXT,
  failed_reason TEXT,
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  FOREIGN KEY (pms_session_id) REFERENCES parking_sessions(pms_session_id),
  UNIQUE (idempotency_key),
  CHECK (amount >= 0),
  CHECK (status IN ('pending', 'success', 'failed', 'cancelled'))
);

CREATE INDEX idx_payment_requests_pms_session_id
ON payment_requests(pms_session_id);

CREATE INDEX idx_payment_requests_status
ON payment_requests(status);

CREATE INDEX idx_payment_requests_carpay_parking_session_id
ON payment_requests(carpay_parking_session_id);

CREATE INDEX idx_payment_requests_carpay_tx_id
ON payment_requests(carpay_tx_id);
```

Logical references:

```text
payment_requests.carpay_parking_session_id
-> Car Pay-in DB.parking_sessions.session_id

payment_requests.carpay_tx_id
-> Car Pay-in DB.transactions.tx_id
```

## 최종 정리

PMS DB는 Mock 주차장 시뮬레이션을 위한 DB이다.
입차 예정 등록은 `pre_registrations`, 입차/출차 정보는 `parking_sessions`, Car Pay-in 결제 요청 및 응답 이력은 `payment_requests`에서 관리한다.

주차장 정보, 게이트 정보, 요금 정책은 DB에 저장하지 않고 서버 코드에서 하드코딩한다.
PMS는 카드 정보나 빌링키를 저장하지 않으며, 결제는 Car Pay-in 서버에 요청한다.

DB가 분리되어 있으므로 Car Pay-in과의 연결은 물리 FK가 아니라 `carpay_parking_session_id`, `carpay_tx_id`를 통한 logical reference로 관리한다.
