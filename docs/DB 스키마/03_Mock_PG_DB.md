# Mock PG DB 스키마

## 개요

Mock PG DB는 PG사를 흉내 내는 Mock 결제대행사 DB이다.
카드 등록 성공 후 발급되는 빌링키와, PG 기준 결제 요청/승인/실패 이력을 관리한다.

Mock Card DB와는 분리된 DB이므로 `card_token`, `card_tx_id`는 물리 FK가 아니라 logical reference로 관리한다.

PostgreSQL에서 `gen_random_uuid()`를 사용하려면 `pgcrypto` 확장이 필요하다.

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

## billing_keys

카드 등록 성공 후 Mock PG가 발급하는 빌링키를 저장한다.
Car Pay-in 서비스는 실제 카드 정보나 카드 토큰 대신 `billing_key`를 저장하고 결제 요청에 사용한다.

`order_id`는 카드 등록 요청의 중복 처리를 막기 위해 unique로 관리한다.

```sql
CREATE TABLE billing_keys (
  billing_key TEXT PRIMARY KEY,
  order_id TEXT UNIQUE NOT NULL,
  card_token TEXT NOT NULL,
  card_last_four CHAR(4) DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status IN ('active', 'inactive'))
);
```

Logical reference:

```text
billing_keys.card_token -> Mock Card DB.card_tokens.card_token
```

## transactions

Mock PG 기준 결제 요청/승인/실패 이력을 저장한다.
Car Pay-in에서 빌링키 결제를 요청하면 PG 거래가 생성되고, 카드사 승인 결과에 따라 상태가 확정된다.

`card_tx_id`를 통해 Mock Card DB의 카드사 거래 이력과 논리적으로 연결할 수 있다.

```sql
CREATE TABLE transactions (
  pg_tx_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  billing_key TEXT NOT NULL,
  card_token TEXT NOT NULL,
  card_tx_id UUID,
  amount INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'KRW',
  approval_no TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  idempotency_key TEXT NOT NULL,
  failed_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ,
  FOREIGN KEY (billing_key) REFERENCES billing_keys(billing_key),
  UNIQUE (idempotency_key),
  CHECK (amount > 0),
  CHECK (status IN ('pending', 'success', 'failed', 'cancelled'))
);
```

Logical reference:

```text
transactions.card_tx_id -> Mock Card DB.tx.tx_id
```

## 최종 정리

Mock PG DB는 Car Pay-in과 Mock Card DB 사이에서 PG 역할을 담당하는 DB이다.
카드 등록 시 Mock Card DB의 `card_token`을 기반으로 `billing_key`를 발급하고, Car Pay-in은 이 `billing_key`만 저장한다.

결제 요청 시 Mock PG는 `billing_key`로 `card_token`을 찾고, Mock Card DB에 카드 승인 요청을 보낸다.
PG 기준 결제 이력은 `transactions`에 저장되며, 카드사 기준 거래는 `card_tx_id`로 추적한다.
