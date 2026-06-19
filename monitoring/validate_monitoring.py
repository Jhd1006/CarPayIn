#!/usr/bin/env python3
"""
CarPayIn 모니터링 스택 설정 검증 스크립트

실행:
  python validate_monitoring.py
  python validate_monitoring.py --skip-http   # Docker 미시작 시 DB만 검증

종료 코드:
  0  모든 검증 통과
  1  하나 이상 실패
"""
import argparse
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable

# ── ANSI 색상 ─────────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}~{RESET} {msg}")


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")
    print("─" * 50)


# ── .env 로드 ─────────────────────────────────────────────────────────────────
def load_env(env_file: Path) -> None:
    if not env_file.exists():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip()


# ── 검증 함수들 ───────────────────────────────────────────────────────────────
def check_env_vars() -> bool:
    section("환경변수 확인")
    required = [
        ("CARPAYIN_DB_URL", "CarPayIn DB"),
        ("MOCK_CARD_DB_URL", "Mock Card DB"),
        ("MOCK_PG_DB_URL", "Mock PG DB"),
        ("PMS_DB_URL", "PMS DB"),
        ("CARPAYIN_REDIS_URL", "CarPayIn Redis"),
        ("PMS_REDIS_URL", "PMS Redis"),
    ]
    all_ok = True
    for var, label in required:
        val = os.getenv(var, "").strip()
        if val:
            ok(f"{label} ({var}) = {val[:40]}{'...' if len(val) > 40 else ''}")
        else:
            fail(f"{label} ({var}) 미설정")
            all_ok = False
    return all_ok


def check_db_connections() -> bool:
    section("DB 연결 확인")
    try:
        import psycopg2
    except ImportError:
        warn("psycopg2 미설치 — DB 연결 검증 생략 (pip install psycopg2-binary)")
        return True

    db_map = {
        "carpayin": os.getenv("CARPAYIN_DB_URL", ""),
        "mock_card": os.getenv("MOCK_CARD_DB_URL", ""),
        "mock_pg": os.getenv("MOCK_PG_DB_URL", ""),
        "pms": os.getenv("PMS_DB_URL", ""),
    }
    all_ok = True
    for db_name, url in db_map.items():
        if not url.strip():
            warn(f"{db_name}: URL 미설정, 건너뜀")
            continue
        normalized = url.replace("postgresql+psycopg://", "postgresql://")
        try:
            conn = psycopg2.connect(normalized, connect_timeout=5)
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()[0].split(",")[0]
            conn.close()
            ok(f"{db_name}: 연결 성공 ({version})")
        except Exception as exc:
            fail(f"{db_name}: 연결 실패 — {exc}")
            all_ok = False
    return all_ok


def _http_get(url: str, timeout: int = 5) -> tuple[int, str]:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read(512).decode(errors="replace")


def check_http_endpoints() -> bool:
    section("HTTP 엔드포인트 확인")
    endpoints = [
        ("Prometheus", "http://localhost:9090/-/ready"),
        ("Grafana", "http://localhost:3000/api/health"),
        ("DB Exporter", "http://localhost:9001/metrics"),
        ("Redis Exporter (carpayin)", "http://localhost:9121/metrics"),
        ("Redis Exporter (pms)", "http://localhost:9122/metrics"),
    ]
    all_ok = True
    for label, url in endpoints:
        try:
            status, body = _http_get(url)
            if status == 200:
                ok(f"{label}: HTTP {status}")
            else:
                fail(f"{label}: HTTP {status}")
                all_ok = False
        except Exception as exc:
            fail(f"{label}: 연결 실패 — {exc}")
            all_ok = False
    return all_ok


def check_prometheus_metrics() -> bool:
    section("Prometheus 메트릭 수집 확인")
    try:
        _, body = _http_get(
            "http://localhost:9090/api/v1/query?query=carpayin_db_up"
        )
    except Exception as exc:
        warn(f"Prometheus API 조회 실패 — {exc}")
        return True

    if "carpayin_db_up" in body:
        ok("carpayin_db_up 메트릭 수집 중")
    else:
        fail("carpayin_db_up 메트릭 없음 — db-exporter가 시작되지 않았을 수 있음")
        return False

    try:
        _, body = _http_get(
            "http://localhost:9090/api/v1/query?query=redis_memory_used_bytes"
        )
        if "redis_memory_used_bytes" in body:
            ok("redis_memory_used_bytes 메트릭 수집 중")
        else:
            warn("redis_memory_used_bytes 메트릭 없음 — Redis 미시작 또는 redis_exporter 오류")
    except Exception:
        pass

    return True


def check_grafana_dashboard() -> bool:
    section("Grafana 대시보드 확인")
    try:
        _, body = _http_get("http://localhost:3000/api/health")
        ok("Grafana 응답 정상")
    except Exception as exc:
        fail(f"Grafana 연결 실패 — {exc}")
        return False

    try:
        req = urllib.request.Request(
            "http://localhost:3000/api/dashboards/uid/carpayin-load-test"
        )
        import base64
        creds = base64.b64encode(b"admin:carpayin123").decode()
        req.add_header("Authorization", f"Basic {creds}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            ok("대시보드 'CarPayIn 부하테스트 모니터링' 로드 성공")
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            warn("대시보드를 찾을 수 없음 — Grafana 재시작 후 재시도")
        else:
            fail(f"대시보드 조회 실패 HTTP {e.code}")
        return False
    except Exception as exc:
        warn(f"대시보드 조회 실패 — {exc}")
        return False


# ── 메인 ─────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="CarPayIn 모니터링 스택 검증")
    parser.add_argument(
        "--skip-http",
        action="store_true",
        help="HTTP 엔드포인트 및 Prometheus/Grafana 검증 건너뜀",
    )
    args = parser.parse_args()

    monitoring_dir = Path(__file__).parent
    load_env(monitoring_dir / ".env")

    results: list[bool] = []

    results.append(check_env_vars())
    results.append(check_db_connections())

    if not args.skip_http:
        results.append(check_http_endpoints())
        results.append(check_prometheus_metrics())
        results.append(check_grafana_dashboard())

    passed = sum(results)
    total = len(results)
    print(f"\n{'─' * 50}")
    if all(results):
        print(f"{GREEN}{BOLD}✓ 모든 검증 통과 ({passed}/{total}){RESET}")
    else:
        failed = total - passed
        print(f"{RED}{BOLD}✗ {failed}개 검증 실패 ({passed}/{total} 통과){RESET}")
        print("\n해결 방법:")
        print("  1. .env 파일이 있는지 확인: cp .env.example .env")
        print("  2. carpayin 메인 스택이 실행 중인지 확인: docker compose ps")
        print("  3. 모니터링 스택 재시작: docker compose up -d --build")
        print("  4. 로그 확인: docker compose logs db-exporter")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
