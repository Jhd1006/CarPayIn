#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CarPayIn 독립 차량 시뮬레이터
Webots 외부에서 /sim/location 업데이트 + LPR 자동 트리거
환경변수: BACKEND_URL, PMS_URL, PLATE, LOT_ID
"""
import time, math, json, urllib.request, os
from datetime import datetime, timezone

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
PMS_URL     = os.getenv("PMS_URL",     "http://localhost:8001")
PLATE       = os.getenv("PLATE",       "12\uac003456")   # 12가3456
LOT_ID      = os.getenv("LOT_ID",      "LOT_TEST_01")

# Webots 좌표 → GPS 변환 기준점
PARKING_LOT_X, PARKING_LOT_Y = 53.33, 3.67
REF_LAT, REF_LNG = 37.48544722, 127.03636666
M_PER_LAT = 111_320.0
M_PER_LNG = 111_320.0 * math.cos(math.radians(REF_LAT))

def webots_to_gps(wx, wy):
    dx = wx - PARKING_LOT_X
    dy = wy - PARKING_LOT_Y
    return REF_LAT + dy / M_PER_LAT, REF_LNG + dx / M_PER_LNG

def post_json(url, data):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json; charset=utf-8"}
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[SIM] POST 실패 {url}: {e}", flush=True)
        return None

lpr_triggered = False
last_lpr_time = 0
START_X, START_Y = 70.7, 1.0
t = 0

print(f"[SIM] 시작 - plate={PLATE}, lot={LOT_ID}", flush=True)

while True:
    progress = min(t / 60.0, 1.0)
    wx = START_X + (PARKING_LOT_X - START_X) * progress
    wy = START_Y + (PARKING_LOT_Y - START_Y) * progress
    lat, lng = webots_to_gps(wx, wy)
    dist = math.sqrt((wx - PARKING_LOT_X)**2 + (wy - PARKING_LOT_Y)**2)
    speed = max(0.0, 20.0 * (1.0 - progress))

    post_json(f"{BACKEND_URL}/sim/location", {
        "lat": lat, "lng": lng,
        "speed_kph": speed, "heading": 225.0, "source": "webots"
    })
    print(f"[GPS] dist={dist:.1f}m lat={lat:.6f} lng={lng:.6f} spd={speed:.1f}", flush=True)

    now = time.time()
    if dist <= 4.0 and not lpr_triggered and (now - last_lpr_time) > 30:
        print(f"[LPR] 4m 이내 진입! 트리거", flush=True)
        res = post_json(f"{PMS_URL}/lpr/entry", {
            "plate": PLATE, "lot_id": LOT_ID,
            "entry_time": datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        })
        print(f"[LPR] 응답: {res}", flush=True)
        lpr_triggered = True
        last_lpr_time = now

    if progress >= 1.0:
        print("[SIM] 주차장 도착. 60초 대기 후 재시작...", flush=True)
        time.sleep(60)
        t = 0
        lpr_triggered = False
    else:
        t += 1
        time.sleep(1)
