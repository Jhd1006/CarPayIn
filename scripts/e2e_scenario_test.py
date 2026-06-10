"""
CarPayIn E2E 시나리오 테스트 (올바른 흐름)
Step 3 (카드 등록) ~ Step 5 (결제)
"""
import urllib.request
import json
import time
import hmac
import hashlib
import sys

TOKEN = open("/tmp/carpayin_token.txt").read().strip()
CARPAYIN_BASE = "http://127.0.0.1:8000"
PMS_BASE = "http://pms:8000"
PG_WEBHOOK_SECRET = "mock-pg-webhook-secret"
PMS_WEBHOOK_SECRET = "pms-webhook-secret"


def call(method, path, body=None, extra_headers=None, base_url=CARPAYIN_BASE, no_auth=False):
    headers = {"Content-Type": "application/json"}
    if TOKEN and not no_auth:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if extra_headers:
        for k, v in extra_headers.items():
            if v is None:
                headers.pop(k, None)
            else:
                headers[k] = v
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else None
    req = urllib.request.Request(base_url + path, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"raw": e.read().decode("utf-8", errors="replace")}


def pms(method, path, body=None):
    return call(method, path, body, base_url=PMS_BASE, no_auth=True)


PASS = "✓"
FAIL = "✗"


def check(label, status, body, expected_status=200, check_field=None):
    ok = status == expected_status
    if check_field:
        ok = ok and check_field in body
    symbol = PASS if ok else FAIL
    print(f"  {symbol} {label}: HTTP {status}")
    if not ok:
        print(f"    => {json.dumps(body, ensure_ascii=False)}")
        sys.exit(1)
    return body


# ══════════════════════════════════════
# 초기화: 기존 active 세션 정리 (중복 방지)
# ══════════════════════════════════════
print("\n=== 사전 준비: 기존 세션 정리 ===")
from sqlalchemy import create_engine, text
import os

# CarPayIn Backend DB 정리
db_url = "postgresql+psycopg://dev_user:dev_pass@carpayin-postgres:5432/carpayin_dev"
engine = create_engine(db_url)
with engine.begin() as conn:
    conn.execute(text("UPDATE parking_sessions SET status='cancelled' WHERE car_id='test-car-001' AND status='active'"))
    print("  ✓ Backend: 기존 active 주차 세션 취소 처리")

# PMS DB 정리
pms_db_url = "postgresql+psycopg://dev_user:dev_pass@pms-postgres:5432/pms_dev"
pms_engine = create_engine(pms_db_url)
with pms_engine.begin() as conn:
    conn.execute(text("UPDATE parking_sessions SET status='cancelled' WHERE plate='12가3456' AND status='active'"))
    conn.execute(text("UPDATE pre_registrations SET status='cancelled' WHERE plate='12가3456' AND status='pre_registered'"))
    print("  ✓ PMS: 기존 active 주차 세션/사전등록 정리")

# ══════════════════════════════════════
# Step 3-A: 카드 등록 order 생성
# ══════════════════════════════════════
print("\n=== Step 3: 카드 등록 / Billing Key 저장 ===")

status, body = call("POST", "/card/order", {
    "plate": "12가3456",
    "bank_name": "hyundai",
    "agree_terms": True,
})
order_result = check("카드 order 생성", status, body, 200, "order_id")
order_id = order_result["order_id"]
pg_url = order_result["pg_url"]
print(f"    order_id: {order_id}")
print(f"    pg_url: {pg_url}")

# ══════════════════════════════════════
# Step 3-B: mock-pg에 테스트 카드 등록 (WebView 카드 제출 시뮬레이션)
# → mock-pg가 mock-card를 통해 billing_key 생성 후 carpayin-backend에 webhook 발송
# ══════════════════════════════════════
# mock-pg URL은 내부 네트워크에서 접근
PG_INTERNAL = "http://mock-pg:8000"
status, pg_body = call("POST", "/pg/card-register", {
    "order_id": order_id,
    "card_number": "4111111111111111",
    "expiry": "12/30",
    "cvc": "123",
}, base_url=PG_INTERNAL, no_auth=True)
check("mock-pg 카드 등록 (billing_key 발급 + webhook 발송)", status, pg_body, 200, "billing_key")
real_billing_key = pg_body["billing_key"]
print(f"    billing_key: {real_billing_key[:20]}...")
print(f"    (mock-pg가 carpayin-backend에 webhook 자동 발송됨)")

# ══════════════════════════════════════
# Step 4-A: 입차 사전알림 (Backend → PMS pre-register)
# ══════════════════════════════════════
print("\n=== Step 4: 입차 사전알림 / 주차 세션 생성 ===")

LOT_ID = "LOT_TEST_01"
PLATE = "12가3456"

status, body = call("POST", "/parking/navigate", {
    "lot_id": LOT_ID,
})
check("사전알림 등록 (Backend→PMS pre-register 포함)", status, body, 200, "status")
print(f"    status: {body.get('status')}, lot_id: {body.get('lot_id')}")

# ══════════════════════════════════════
# Step 4-B: PMS LPR 입차 (PMS가 세션 생성 + Backend webhook 호출)
# ══════════════════════════════════════
entry_time = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(time.time() - 3600))
status, lpr_body = pms("POST", "/lpr/entry", {
    "lot_id": LOT_ID,
    "plate": PLATE,
    "entry_time": entry_time,
})
lpr_result = check("PMS LPR 입차 (PMS session 생성 + Backend 웹훅)", status, lpr_body, 200, "pms_session_id")
pms_session_id = lpr_result["pms_session_id"]
print(f"    pms_session_id: {pms_session_id}")
print(f"    status: {lpr_result.get('status')}")

# Backend가 parking session을 만들었는지 확인
time.sleep(0.5)
with engine.begin() as conn:
    rows = conn.execute(text(
        "SELECT session_id, pms_session_id, status FROM parking_sessions WHERE car_id='test-car-001' AND status='active'"
    )).fetchall()
    if rows:
        SESSION_ID = str(rows[0][0])
        print(f"    Backend session_id: {SESSION_ID}")
        print(f"  ✓ Backend parking session 생성 확인")
    else:
        print("  ✗ Backend parking session 없음")
        sys.exit(1)

# ══════════════════════════════════════
# Step 5: 요금 조회
# ══════════════════════════════════════
print("\n=== Step 5: 요금 조회 / 결제 ===")

time.sleep(1)

status, body = call("GET", f"/fee/{SESSION_ID}")
fee_result = check("요금 조회 (Backend→PMS fee 계산)", status, body, 200, "amount")
amount = fee_result["amount"]
currency = fee_result["currency"]
print(f"    amount: {amount} {currency}")
print(f"    duration: {fee_result.get('duration')}분")
print(f"    entry_time: {fee_result.get('entry_time')}")

# ══════════════════════════════════════
# Step 5-B: 결제 처리 (Backend→PG→Card→PMS notify)
# ══════════════════════════════════════
status, body = call("POST", "/payment", {
    "session_id": SESSION_ID,
    "amount": amount,
    "currency": currency,
})
payment_result = check("결제 처리 (PG 승인 + PMS paid 통보)", status, body, 200, "status")
print(f"    status: {payment_result.get('status')}")
print(f"    tx_id: {payment_result.get('tx_id')}")
print(f"    approval_no: {payment_result.get('approval_no')}")
print(f"    amount: {payment_result.get('amount')} {payment_result.get('currency')}")

# ══════════════════════════════════════
# 최종 상태 확인
# ══════════════════════════════════════
with engine.begin() as conn:
    row = conn.execute(text(
        f"SELECT status FROM parking_sessions WHERE session_id='{SESSION_ID}'"
    )).fetchone()
    if row and row[0] == "completed":
        print(f"  ✓ parking_session status: {row[0]}")
    else:
        print(f"  ✗ parking_session status: {row[0] if row else 'not found'}")

print("\n✓ 모든 시나리오 단계 완료!")
