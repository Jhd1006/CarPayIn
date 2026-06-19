# CarPayIn 모니터링 가이드

## 대시보드 구성

### 상단 요약 패널 (6개 stat)

| 패널 | 메트릭 | 정상 기준 |
|---|---|---|
| DB 연결 상태 | `sum(carpayin_db_up)` | 4/4 |
| Active DB 연결 | `sum(carpayin_db_connections{state="active"})` | < 20 |
| 진행중 주차세션 | `carpayin_parking_sessions{status="active"}` | 부하량에 비례 |
| 결제 성공 | `carpayin_transactions{status="success"}` | 지속 증가 |
| 결제 실패 | `carpayin_transactions{status="failed"}` | 0 유지 |
| 최대 쿼리 지연 | `max(carpayin_db_longest_query_seconds)` | < 1s |

---

### DB 연결 현황

**Active 연결** — 쿼리를 실제 실행 중인 연결 수. 부하 테스트 중 급증하면 DB가 병목임을 의미합니다.

**Idle in Transaction** — 트랜잭션을 열어둔 채 아무것도 하지 않는 연결. 이 수치가 높으면 애플리케이션 코드에서 트랜잭션을 제대로 닫지 않는 문제가 있습니다.

---

### 주차 / 결제 흐름

**주차세션 상태 추이**
- `active` 증가 → 입차 처리 중
- `completed` 증가 → 결제 후 출차 완료
- `cancelled` 증가 → 비정상 흐름 (확인 필요)

**결제 트랜잭션 상태 추이**
- `success` 와 `failed` 비율로 결제 성공률 모니터링
- `pending` 이 오래 유지되면 PG 응답 지연 의심

**알림 아웃박스 상태 추이**

IoT/MQTT 알림 전달 파이프라인을 추적합니다.

```
pending → publishing → published → delivered
                    ↘ failed (→ 재시도 최대 5회) → dead
```

- `dead` 증가 → Android 앱에 결제 완료 알림이 전달되지 않음
- `failed` 증가 → SQS/IoT Core 연결 문제 또는 일시적 장애

**PMS 주차/결제 상태 추이**

carpayin DB의 트랜잭션과 PMS DB의 payment_requests를 비교하면 두 시스템 간 동기화 상태를 확인할 수 있습니다.

---

### DB 성능

**Commit 속도** — `rate(carpayin_db_xact_commit[30s])`

부하 테스트 중 이 수치가 기대 TPS보다 낮으면 DB가 처리량 병목입니다.

**가장 긴 쿼리 실행 시간**

1초 이상 유지되는 경우:
1. `pg_stat_activity` 직접 조회하여 해당 쿼리 확인
2. `EXPLAIN ANALYZE` 로 쿼리 플랜 분석
3. 인덱스 누락 여부 확인 (`idx_parking_sessions_status`, `idx_transactions_session_id` 등)

**데드락 발생**

부하 테스트 중 데드락이 반복되면 주차 세션 생성과 결제 처리 간의 트랜잭션 순서 문제를 의심하세요.

---

### Redis

**메모리 사용량**

carpayin Redis에는 다음이 저장됩니다:
- QR 세션 (15분 TTL)
- OAuth state (단기 TTL)
- 카드 등록 주문 (단기 TTL)
- Pre-notify 정보 (입차 전 차량 정보)
- Fee quote 캐시 (30초 TTL)
- 알림 재시도 큐

부하 테스트 중 메모리가 급증하면 TTL 설정이나 키 누수를 확인하세요.

**명령 처리 속도**

carpayin Redis는 결제 흐름마다 여러 번 접근합니다. ops/s 가 TPS의 10배 이상이면 정상입니다.

---

### 환경별 설정

#### 로컬 Docker Compose

`.env` 기본값 사용. `host.docker.internal`이 메인 스택의 DB/Redis를 가리킵니다.

#### AWS 환경

`.env`에서 아래 값을 실제 AWS 주소로 교체:

```
CARPAYIN_DB_URL=postgresql://carpayin:<pw>@<rds-endpoint>:5432/carpayin
MOCK_PG_DB_URL=postgresql://dev_user:<pw>@<mock-pg-ec2-private-ip>:5432/mock_pg_dev
PMS_DB_URL=postgresql://dev_user:<pw>@<pms-ec2-private-ip>:5432/pms_dev
CARPAYIN_REDIS_URL=redis://<elasticache-endpoint>:6379
PMS_REDIS_URL=redis://<pms-elasticache-endpoint>:6379
```

Mock Card DB가 OpenStack에 있는 경우, WireGuard 터널을 통한 IP 주소를 사용합니다.

---

## Prometheus 직접 조회

`http://localhost:9090` 에서 PromQL로 원하는 메트릭을 바로 조회할 수 있습니다.

**유용한 쿼리 예시:**

```promql
# 지난 5분간 결제 성공 건수
increase(carpayin_transactions{status="success"}[5m])

# DB별 트랜잭션 처리율 (TPS)
rate(carpayin_db_xact_commit[1m])

# Redis 캐시 히트율
rate(redis_keyspace_hits_total[1m]) /
  (rate(redis_keyspace_hits_total[1m]) + rate(redis_keyspace_misses_total[1m]))

# 현재 DB별 total 연결 수 (active + idle)
sum by (db_name) (carpayin_db_connections)
```

---

## 부하 테스트 체크리스트

테스트 시작 전:
- [ ] `carpayin_db_up` 4개 모두 1인지 확인
- [ ] 모든 Redis exporter `UP` 상태 확인 (`http://localhost:9090/targets`)
- [ ] `carpayin_parking_sessions{status="active"}` 초기값 확인

테스트 중 모니터링:
- [ ] Active DB 연결 급증 여부
- [ ] `failed` 트랜잭션 0 유지
- [ ] `longest_query_seconds` < 1s
- [ ] `notification_outbox{status="dead"}` 0 유지

테스트 후 확인:
- [ ] `pending` 트랜잭션 모두 해소됐는지 확인
- [ ] `outbox{status="dead"}` 없는지 확인
- [ ] PMS `payment_requests{status="success"}` ≈ carpayin `transactions{status="success"}`
