#!/usr/bin/env python3
"""
CarPayIn DB Metrics Exporter

각 서비스 PostgreSQL DB에서 인프라 메트릭과 비즈니스 메트릭을 수집하여
Prometheus 형식으로 :9001/metrics 에 노출합니다.

수집 대상:
  - carpayin  : 주 백엔드 DB (parking_sessions, transactions, outbox)
  - mock_card : Mock 카드사 DB (cards, card_tokens)
  - mock_pg   : Mock PG DB (billing_keys)
  - pms       : 주차 관리 시스템 DB (parking_sessions, payment_requests)
"""
import logging
import os
import threading
import time

import psycopg2
from prometheus_client import Gauge, start_http_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("carpayin.db_exporter")

# ── 설정 ─────────────────────────────────────────────────────────────────────
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL_SECONDS", "5"))
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9001"))

DB_URLS: dict[str, str] = {
    "carpayin": os.getenv("CARPAYIN_DB_URL", ""),
    "mock_card": os.getenv("MOCK_CARD_DB_URL", ""),
    "mock_pg": os.getenv("MOCK_PG_DB_URL", ""),
    "pms": os.getenv("PMS_DB_URL", ""),
}

# ── 인프라 메트릭 ─────────────────────────────────────────────────────────────
g_up = Gauge(
    "carpayin_db_up",
    "DB 연결 상태 (1=연결, 0=실패)",
    ["db_name"],
)
g_conns = Gauge(
    "carpayin_db_connections",
    "상태별 DB 연결 수",
    ["db_name", "state"],
)
g_xact_commit = Gauge(
    "carpayin_db_xact_commit",
    "누적 커밋 수 (rate()로 속도 계산)",
    ["db_name"],
)
g_xact_rollback = Gauge(
    "carpayin_db_xact_rollback",
    "누적 롤백 수",
    ["db_name"],
)
g_deadlocks = Gauge(
    "carpayin_db_deadlocks",
    "누적 데드락 수",
    ["db_name"],
)
g_longest_query = Gauge(
    "carpayin_db_longest_query_seconds",
    "현재 가장 오래 실행 중인 쿼리 시간 (초)",
    ["db_name"],
)
g_size = Gauge(
    "carpayin_db_size_bytes",
    "데이터베이스 크기 (bytes)",
    ["db_name"],
)
g_table_rows = Gauge(
    "carpayin_db_table_rows",
    "테이블 예상 행 수 (pg_stat_user_tables)",
    ["db_name", "table_name"],
)
g_scrape_duration = Gauge(
    "carpayin_db_scrape_duration_seconds",
    "스크레이프 소요 시간 (초)",
    ["db_name"],
)
g_scrape_errors = Gauge(
    "carpayin_db_scrape_errors",
    "누적 스크레이프 오류 수",
    ["db_name"],
)

# ── 비즈니스 메트릭 — carpayin ────────────────────────────────────────────────
g_parking_sessions = Gauge(
    "carpayin_parking_sessions",
    "주차 세션 수 by 상태 (active/completed/cancelled)",
    ["status"],
)
g_transactions = Gauge(
    "carpayin_transactions",
    "결제 트랜잭션 수 by 상태 (pending/success/failed/cancelled)",
    ["status"],
)
g_outbox = Gauge(
    "carpayin_notification_outbox",
    "알림 아웃박스 항목 수 by 상태",
    ["status"],
)
g_users = Gauge("carpayin_users_total", "등록된 사용자 수")
g_vehicles = Gauge("carpayin_vehicles_total", "등록된 차량 수")
g_billing_keys = Gauge(
    "carpayin_billing_keys",
    "빌링키 수 by 상태 (active/inactive)",
    ["status"],
)

# ── 비즈니스 메트릭 — pms ─────────────────────────────────────────────────────
g_pms_sessions = Gauge(
    "pms_parking_sessions",
    "PMS 주차 세션 수 by 상태 (active/paid/exited/cancelled)",
    ["status"],
)
g_pms_payment_requests = Gauge(
    "pms_payment_requests",
    "PMS 결제 요청 수 by 상태 (pending/success/failed/cancelled)",
    ["status"],
)

# ── 비즈니스 메트릭 — mock_card ───────────────────────────────────────────────
g_mockcard_cards = Gauge(
    "mockcard_cards",
    "Mock 카드사 카드 수 by 상태 (active/inactive/expired)",
    ["status"],
)
g_mockcard_tx = Gauge(
    "mockcard_tx",
    "Mock 카드사 거래 수 by 상태 (success/failed/cancelled)",
    ["status"],
)

# ── 비즈니스 메트릭 — mock_pg ─────────────────────────────────────────────────
g_mockpg_transactions = Gauge(
    "mockpg_transactions",
    "Mock PG 거래 수 by 상태 (pending/success/failed/cancelled)",
    ["status"],
)

# ── 내부 상태 ─────────────────────────────────────────────────────────────────
_error_counts: dict[str, int] = {k: 0 for k in DB_URLS}


def _normalize_url(url: str) -> str:
    """SQLAlchemy psycopg3 URL → psycopg2 URL."""
    return url.replace("postgresql+psycopg://", "postgresql://")


def _connect(url: str):
    conn = psycopg2.connect(_normalize_url(url), connect_timeout=5)
    conn.autocommit = True
    return conn


# ── 인프라 스크레이퍼 ─────────────────────────────────────────────────────────
def _scrape_infra(conn, db_name: str) -> None:
    with conn.cursor() as cur:
        # 상태별 연결 수
        cur.execute("""
            SELECT COALESCE(state, 'unknown'), COUNT(*)
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND pid <> pg_backend_pid()
            GROUP BY state
        """)
        for state in ("active", "idle", "idle in transaction",
                      "idle in transaction (aborted)", "unknown"):
            g_conns.labels(db_name=db_name, state=state).set(0)
        for state, count in cur.fetchall():
            g_conns.labels(db_name=db_name, state=state).set(count)

        # DB 레벨 통계 (pg_stat_database)
        cur.execute("""
            SELECT xact_commit, xact_rollback, deadlocks,
                   pg_database_size(datname)
            FROM pg_stat_database
            WHERE datname = current_database()
        """)
        row = cur.fetchone()
        if row:
            g_xact_commit.labels(db_name=db_name).set(row[0])
            g_xact_rollback.labels(db_name=db_name).set(row[1])
            g_deadlocks.labels(db_name=db_name).set(row[2])
            g_size.labels(db_name=db_name).set(row[3])

        # 가장 오래 실행 중인 쿼리 시간
        cur.execute("""
            SELECT COALESCE(
                MAX(EXTRACT(EPOCH FROM (now() - query_start))), 0
            )
            FROM pg_stat_activity
            WHERE state = 'active'
              AND datname = current_database()
              AND pid <> pg_backend_pid()
              AND query NOT LIKE '%pg_stat_activity%'
        """)
        row = cur.fetchone()
        g_longest_query.labels(db_name=db_name).set(row[0] if row else 0)

        # 테이블별 행 수 (상위 20개)
        cur.execute("""
            SELECT relname, n_live_tup
            FROM pg_stat_user_tables
            ORDER BY n_live_tup DESC
            LIMIT 20
        """)
        for table_name, rows in cur.fetchall():
            g_table_rows.labels(db_name=db_name, table_name=table_name).set(rows)


# ── 비즈니스 스크레이퍼 ───────────────────────────────────────────────────────
def _scrape_carpayin(conn) -> None:
    with conn.cursor() as cur:
        # parking_sessions: active / completed / cancelled
        cur.execute("SELECT status, COUNT(*) FROM parking_sessions GROUP BY status")
        for s in ("active", "completed", "cancelled"):
            g_parking_sessions.labels(status=s).set(0)
        for status, count in cur.fetchall():
            g_parking_sessions.labels(status=status).set(count)

        # transactions: pending / success / failed / cancelled
        cur.execute("SELECT status, COUNT(*) FROM transactions GROUP BY status")
        for s in ("pending", "success", "failed", "cancelled"):
            g_transactions.labels(status=s).set(0)
        for status, count in cur.fetchall():
            g_transactions.labels(status=status).set(count)

        # payment_notification_outbox
        cur.execute(
            "SELECT status, COUNT(*) FROM payment_notification_outbox GROUP BY status"
        )
        for s in ("pending", "publishing", "published", "delivered", "failed", "dead"):
            g_outbox.labels(status=s).set(0)
        for status, count in cur.fetchall():
            g_outbox.labels(status=status).set(count)

        # 사용자/차량 수
        cur.execute("SELECT COUNT(*) FROM users")
        g_users.set(cur.fetchone()[0])

        cur.execute("SELECT COUNT(*) FROM vehicles")
        g_vehicles.set(cur.fetchone()[0])

        # vehicle_billing_keys: active / inactive
        cur.execute(
            "SELECT status, COUNT(*) FROM vehicle_billing_keys GROUP BY status"
        )
        for s in ("active", "inactive"):
            g_billing_keys.labels(status=s).set(0)
        for status, count in cur.fetchall():
            g_billing_keys.labels(status=status).set(count)


def _scrape_pms(conn) -> None:
    with conn.cursor() as cur:
        # parking_sessions: active / paid / exited / cancelled
        cur.execute("SELECT status, COUNT(*) FROM parking_sessions GROUP BY status")
        for s in ("active", "paid", "exited", "cancelled"):
            g_pms_sessions.labels(status=s).set(0)
        for status, count in cur.fetchall():
            g_pms_sessions.labels(status=status).set(count)

        # payment_requests: pending / success / failed / cancelled
        cur.execute(
            "SELECT status, COUNT(*) FROM payment_requests GROUP BY status"
        )
        for s in ("pending", "success", "failed", "cancelled"):
            g_pms_payment_requests.labels(status=s).set(0)
        for status, count in cur.fetchall():
            g_pms_payment_requests.labels(status=status).set(count)


def _scrape_mockcard(conn) -> None:
    with conn.cursor() as cur:
        # cards: active / inactive / expired
        cur.execute("SELECT status, COUNT(*) FROM cards GROUP BY status")
        for s in ("active", "inactive", "expired"):
            g_mockcard_cards.labels(status=s).set(0)
        for status, count in cur.fetchall():
            g_mockcard_cards.labels(status=status).set(count)

        # tx: success / failed / cancelled
        cur.execute("SELECT status, COUNT(*) FROM tx GROUP BY status")
        for s in ("success", "failed", "cancelled"):
            g_mockcard_tx.labels(status=s).set(0)
        for status, count in cur.fetchall():
            g_mockcard_tx.labels(status=status).set(count)


def _scrape_mockpg(conn) -> None:
    with conn.cursor() as cur:
        # transactions: pending / success / failed / cancelled
        cur.execute("SELECT status, COUNT(*) FROM transactions GROUP BY status")
        for s in ("pending", "success", "failed", "cancelled"):
            g_mockpg_transactions.labels(status=s).set(0)
        for status, count in cur.fetchall():
            g_mockpg_transactions.labels(status=status).set(count)


BUSINESS_SCRAPERS = {
    "carpayin": _scrape_carpayin,
    "pms": _scrape_pms,
    "mock_card": _scrape_mockcard,
    "mock_pg": _scrape_mockpg,
}


# ── 스크레이프 루프 ───────────────────────────────────────────────────────────
def scrape_once(db_name: str, url: str) -> None:
    start = time.monotonic()
    try:
        conn = _connect(url)
        try:
            _scrape_infra(conn, db_name)
            scraper = BUSINESS_SCRAPERS.get(db_name)
            if scraper:
                scraper(conn)
        finally:
            conn.close()
        g_up.labels(db_name=db_name).set(1)
    except Exception as exc:
        logger.warning("scrape_failed db=%s error=%s", db_name, exc)
        g_up.labels(db_name=db_name).set(0)
        _error_counts[db_name] += 1
        g_scrape_errors.labels(db_name=db_name).set(_error_counts[db_name])
    finally:
        g_scrape_duration.labels(db_name=db_name).set(time.monotonic() - start)


def _run_loop(db_name: str, url: str) -> None:
    logger.info("scraper_started db=%s interval=%ds", db_name, SCRAPE_INTERVAL)
    while True:
        scrape_once(db_name, url)
        time.sleep(SCRAPE_INTERVAL)


def main() -> None:
    configured = {k: v for k, v in DB_URLS.items() if v.strip()}
    if not configured:
        logger.error(
            "DB URL이 하나도 설정되지 않았습니다. "
            "CARPAYIN_DB_URL, MOCK_CARD_DB_URL, MOCK_PG_DB_URL, PMS_DB_URL 중 "
            "하나 이상을 .env 에 설정하세요."
        )
        raise SystemExit(1)

    logger.info(
        "exporter_starting port=%d dbs=%s interval=%ds",
        EXPORTER_PORT,
        list(configured),
        SCRAPE_INTERVAL,
    )
    start_http_server(EXPORTER_PORT)

    threads = [
        threading.Thread(
            target=_run_loop,
            args=(db_name, url),
            daemon=True,
            name=f"scraper-{db_name}",
        )
        for db_name, url in configured.items()
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
