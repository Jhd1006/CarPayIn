# PMS DB 스키마

## 개요

PMS DB는 Mock 주차장 시스템에서 사용하는 간소화된 DB이다.
차량 입차/출차 세션, Car Pay-in 결제 요청 이력을 관리한다.

사전등록(pre-registration)은 임시 상태이므로 DB에 저장하지 않고 pms-redis에 TTL 기반으로 관리한다.
Redis key 설계는 `docs/DB schemas/05_Redis_Keys.md` 참고.

주차장은 UI상 여러 개처럼 보일 수 있지만, 실제 시뮬레이션에서는 하나의 Mock 주차장으로 처리한다.
따라서 주차장 정보, 게이트 정보, 요금 정책은 DB에 저장하지 않고 서버 코드에서 하드코딩한다.

PMS는 카드 정보나 빌링키를 저장하지 않는다.
차량은 차량번호 `plate` 기준으로 식별하고, 결제가 필요한 시점에 Car Pay-in 서비스로 결제를 요청한다.

Car Pay-in DB와는 분리된 DB이므로 `carpay_parking_session_id`, `carpay_tx_id`는 물리 FK가 아니라 logical reference로 관리한다.

PostgreSQL에서 `gen_random_uuid()`를 사용하려면 `pgcrypto` 확장이 필요하다.

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

## parking_sessions

PMS 기준 주차 세션 정보를 저장한다.
Car Pay-in 사용자 여부와 관계없이 LPR이 인식한 모든 차량의 입차/출차 세션을 관리한다.

동일 차량번호는 active 주차 세션을 1개만 가질 수 있다.

상태 전이:
- `active`: 입차 후 결제 전
- `paid`: Car Pay-in에서 사전 결제 완료 통보를 받은 상태, 출차 차단기 개방 대기 중
- `exited`: 출차 LPR 확인 후 차단기 개방 완료, `exit_time` 기록됨
- `cancelled`: 취소된 세션

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
  CHECK (status IN ('active', 'paid', 'exited', 'cancelled'))
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
입차/출차 정보는 `parking_sessions`, Car Pay-in 결제 완료 이력은 `payment_requests`에서 관리한다.

사전등록은 임시 상태이므로 DB 테이블이 아닌 pms-redis에 `pre_reg:{lot_id}:{plate}` 키로 TTL 1시간 관리한다. migration `003_drop_pre_registrations`로 제거되었다.

LPR은 모든 차량에 차단기를 열고 세션을 생성한다. Car Pay-in 사전 등록 차량(Redis에 키 존재)만 백엔드 webhook을 받는다.
출차 시 pms-redis `parking_session:{lot_id}:{plate}` 키의 상태가 `paid`이어야 출구 차단기가 열린다. Redis 키 유실 시 DB를 fallback으로 조회한다. 결제되지 않은 차량은 차단기가 열리지 않는다.

Redis는 실시간 상태판(입차→active, 결제→paid, 출차→삭제), DB는 영구 이력 전용으로 책임을 분리한다.

주차장 정보, 게이트 정보, 요금 정책은 DB에 저장하지 않고 서버 코드에서 하드코딩한다.
PMS는 카드 정보나 빌링키를 저장하지 않으며, 결제는 Car Pay-in 서버에 요청한다.

DB가 분리되어 있으므로 Car Pay-in과의 연결은 물리 FK가 아니라 `carpay_parking_session_id`, `carpay_tx_id`를 통한 logical reference로 관리한다.
