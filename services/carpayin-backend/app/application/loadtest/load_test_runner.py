"""
load_test_runner.py

CarPayIn 전체 흐름 부하테스트 스크립트 (동시 N명)

흐름:
  1. POST /dev/seed-test-user (1회, count=N)
  2. 각 유저별 동시에:
     a. POST /parking/navigate          (CarPayIn - pre-notify + Redis 등록)
     b. POST /parking/pre-register      (PMS)
     c. POST /lpr/entry                 (PMS → CarPayIn /webhook/entry 자동 호출)
     d. GET  /fee/{session_id}          (CarPayIn)
     e. POST /payment                   (CarPayIn)
  3. POST /dev/reset (선택, 테스트 후 초기화)
"""

import asyncio
from datetime import datetime, timezone, timedelta

import httpx

# ── 설정 ────────────────────────────────────────────────────────────────────

CARPAYIN_URL     = "http://hd-public-alb-204074971.ap-northeast-2.elb.amazonaws.com"
PMS_URL          = "http://mockpms-public-alb-810192222.ap-northeast-2.elb.amazonaws.com"
LOT_ID           = "LOT_GANGNAM_01"
CONCURRENT_USERS = 5
ENTRY_TIME       = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")

# ── 단계별 함수 ──────────────────────────────────────────────────────────────

async def step_navigate(client: httpx.AsyncClient, user: dict) -> bool:
    resp = await client.post(
        f"{CARPAYIN_URL}/parking/navigate",
        json={"lot_id": LOT_ID},
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )
    if resp.status_code != 200:
        print(f"  [navigate] 실패 {resp.status_code}: {resp.text}")
        return False
    print(f"  [navigate] OK")
    return True


async def step_pms_pre_register(client: httpx.AsyncClient, user: dict) -> bool:
    resp = await client.post(
        f"{PMS_URL}/parking/pre-register",
        json={"lot_id": LOT_ID, "plate": user["plate"]},
    )
    if resp.status_code != 200:
        print(f"  [pms pre-register] 실패 {resp.status_code}: {resp.text}")
        return False
    print(f"  [pms pre-register] OK")
    return True


async def step_lpr_entry(client: httpx.AsyncClient, user: dict) -> str | None:
    resp = await client.post(
        f"{PMS_URL}/lpr/entry",
        json={"lot_id": LOT_ID, "plate": user["plate"], "entry_time": ENTRY_TIME},
    )
    if resp.status_code != 200:
        print(f"  [lpr/entry] 실패 {resp.status_code}: {resp.text}")
        return None
    pms_session_id = resp.json().get("pms_session_id")
    print(f"  [lpr/entry] OK — pms_session_id={pms_session_id}")
    return pms_session_id


async def step_get_session_id(client: httpx.AsyncClient, user: dict) -> str | None:
    resp = await client.get(
        f"{CARPAYIN_URL}/dev/parking-session",
        params={"car_id": user["car_id"]},
    )
    if resp.status_code != 200:
        print(f"  [session 조회] 실패 {resp.status_code}: {resp.text}")
        return None
    session_id = resp.json().get("session_id")
    print(f"  [session 조회] OK — session_id={session_id}")
    return session_id


async def step_get_fee(client: httpx.AsyncClient, user: dict, session_id: str) -> int | None:
    resp = await client.get(
        f"{CARPAYIN_URL}/fee/{session_id}",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )
    if resp.status_code != 200:
        print(f"  [fee] 실패 {resp.status_code}: {resp.text}")
        return None
    amount = resp.json().get("amount")
    print(f"  [fee] OK — amount={amount}")
    return amount


async def step_payment(client: httpx.AsyncClient, user: dict, session_id: str, amount: int) -> bool:
    resp = await client.post(
        f"{CARPAYIN_URL}/payment",
        json={"session_id": session_id, "amount": amount, "currency": "KRW"},
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )
    data = resp.json()
    if resp.status_code == 402 or data.get("status") == "failed":
        print(f"  [payment] 결제실패 — {data.get('failed_reason')}")
        return False
    if resp.status_code != 200:
        print(f"  [payment] 오류 {resp.status_code}: {resp.text}")
        return False
    print(f"  [payment] OK — tx_id={data.get('tx_id')} approval_no={data.get('approval_no')}")
    return True


# ── 유저 1명 전체 흐름 ────────────────────────────────────────────────────────

STEPS = ["navigate", "pms_pre_register", "lpr_entry", "session_조회", "fee", "payment"]

async def run_user_flow(client: httpx.AsyncClient, user: dict) -> dict:
    """유저 1명 흐름 실행. 결과 dict 반환."""
    plate = user["plate"]
    result = {"plate": plate, "success": False, "failed_at": None}
    print(f"\n[{plate}] 시작")

    if not await step_navigate(client, user):
        result["failed_at"] = "navigate"
        return result

    if not await step_pms_pre_register(client, user):
        result["failed_at"] = "pms_pre_register"
        return result

    pms_session_id = await step_lpr_entry(client, user)
    if not pms_session_id:
        result["failed_at"] = "lpr_entry"
        return result

    await asyncio.sleep(1)

    session_id = await step_get_session_id(client, user)
    if not session_id:
        result["failed_at"] = "session_조회"
        return result

    amount = await step_get_fee(client, user, session_id)
    if amount is None:
        result["failed_at"] = "fee"
        return result

    ok = await step_payment(client, user, session_id, amount)
    if not ok:
        result["failed_at"] = "payment"
        return result

    result["success"] = True
    return result


# ── 메인 ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:

        # 1. 시드 데이터 생성
        print(f"=== 시드 데이터 생성 (count={CONCURRENT_USERS}) ===")
        resp = await client.post(
            f"{CARPAYIN_URL}/dev/seed-test-user",
            json={"count": CONCURRENT_USERS, "lot_id": LOT_ID},
        )
        if resp.status_code != 200:
            print(f"시드 실패: {resp.status_code} {resp.text}")
            return

        users = resp.json()["users"]
        print(f"시드 완료: {len(users)}명")

        # 2. 동시 실행
        print("\n=== 전체 흐름 동시 실행 ===")
        results = await asyncio.gather(*[run_user_flow(client, u) for u in users])

        # 3. 결과 요약
        success = [r for r in results if r["success"]]
        failed  = [r for r in results if not r["success"]]

        print("\n" + "=" * 50)
        print(f"  총 {len(results)}명 | 성공 {len(success)}명 | 실패 {len(failed)}명")
        print("=" * 50)

        if failed:
            print("\n[실패 목록]")
            for r in failed:
                print(f"  plate={r['plate']} — {r['failed_at']} 단계에서 실패")

        if success:
            print("\n[성공 목록]")
            for r in success:
                print(f"  plate={r['plate']} — 전체 흐름 완료")

        print()

        # # 4. (선택) 테스트 후 초기화 — 주석 해제하면 DB/Redis 전체 삭제
        # await client.post(f"{CARPAYIN_URL}/dev/reset")
        # await client.post(f"{PMS_URL}/dev/reset")
        # print("초기화 완료")


if __name__ == "__main__":
    asyncio.run(main())