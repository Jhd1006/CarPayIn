# Mock Card DB 스키마

## 개요

Mock Card DB는 실제 카드사를 흉내 내는 Mock 카드사 DB이다.
사용자, 실제 카드 정보, 카드 토큰, 카드사 기준 결제 승인/실패 이력을 관리한다.

Mock 환경에서는 카드번호를 그대로 저장하지 않고 `encrypted_card_num`으로 저장하며, `cvc_hmac`는 Mock 검증 용도로만 사용한다.

PostgreSQL에서 `gen_random_uuid()`를 사용하려면 `pgcrypto` 확장이 필요하다.

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

## users

Mock 카드사 기준 사용자 정보를 저장한다.
사용자 식별자인 `user_id`, 이름, 생성 시각을 관리한다.

```sql
CREATE TABLE users (
  user_id TEXT PRIMARY KEY,
  name TEXT DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## cards

Mock 카드사에 등록된 실제 카드 정보를 저장한다.
카드번호는 원문이 아니라 `encrypted_card_num`으로 저장한다.

동일 사용자가 같은 카드번호를 중복 등록하지 못하도록 `user_id`, `encrypted_card_num` 조합에 unique 제약을 둔다.

```sql
CREATE TABLE cards (
  card_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  encrypted_card_num TEXT NOT NULL,
  cvc_hmac TEXT,
  exp_month INTEGER NOT NULL,
  exp_year INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (user_id) REFERENCES users(user_id),
  UNIQUE (user_id, encrypted_card_num),
  CHECK (exp_month BETWEEN 1 AND 12),
  CHECK (status IN ('active', 'inactive', 'expired'))
);
```

## card_tokens

PG/결제 승인 요청에서 사용할 카드 토큰을 저장한다.
실제 카드 정보 대신 `card_token`을 통해 카드사를 호출하도록 한다.

```sql
CREATE TABLE card_tokens (
  card_token TEXT PRIMARY KEY,
  card_id UUID NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (card_id) REFERENCES cards(card_id),
  CHECK (status IN ('active', 'inactive'))
);
```

## tx

Mock 카드사 기준 결제 승인/실패 이력을 저장한다.
PG가 `card_token`으로 결제 승인을 요청하면 카드사 기준 거래 이력이 생성된다.

`idempotency_key`는 동일 결제 요청의 중복 처리를 막기 위해 사용한다.

```sql
CREATE TABLE tx (
  tx_id TEXT PRIMARY KEY,
  card_token TEXT NOT NULL,
  amount INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'KRW',
  approval_no TEXT,
  status TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (card_token) REFERENCES card_tokens(card_token),
  UNIQUE (idempotency_key),
  CHECK (amount > 0),
  CHECK (status IN ('success', 'failed', 'cancelled'))
);
```

## 최종 정리

Mock Card DB는 실제 카드사 역할을 하는 DB이다.
카드 원본 정보는 저장하지 않고 암호화된 카드번호와 Mock 검증용 CVC HMAC만 저장한다.

PG는 실제 카드 정보가 아니라 `card_token`으로 카드사에 결제 승인을 요청한다.
카드사 기준 결제 결과는 `tx`에 저장되며, 이 거래는 Mock PG DB의 `transactions.card_tx_id`와 논리적으로 연결된다.
