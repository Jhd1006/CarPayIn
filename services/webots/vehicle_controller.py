"""
vehicle_controller.py – Webots 차량 컨트롤러 (Android 내비게이션 연동)
"""

from controller import Robot, GPS
from datetime import datetime, timezone
import math
import threading
import time
import json
import pathlib
import sys
import subprocess

SERVER_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
from shared_config import get_config

try:
    import httpx
    _HTTP_LIB = "httpx"
except ImportError:
    import urllib.request
    _HTTP_LIB = "urllib"

# ── 설정 ─────────────────────────────────────────────────────────────
BACKEND_URL = get_config("BACKEND_URL", "http://localhost:8000")
PMS_URL     = get_config("PARKING_PMS_URL", "http://localhost:8001")

VIN          = get_config("WEBOTS_VIN", "TESTVIN001")
PLATE        = get_config("WEBOTS_PLATE", "123가4567")
LOT_ID       = get_config("WEBOTS_LOT_ID", "LOT_TEST_01")

PARKING_LOT_X, PARKING_LOT_Z = 53.33, 3.67
LPR_THRESHOLD        = 4.0
DEFAULT_SPEED        = 5.0

# ── 상태 변수 ────────────────────────────────────────────────────────
_lpr_triggered     = False
_last_lpr_time     = 0.0
_cooldown_s        = 30.0

# ── GPS 좌표 변환 ────────────────────────────────────────────────────
REF_LAT, REF_LNG = 37.493087, 127.049750
REF_WX, REF_WZ   = PARKING_LOT_X, PARKING_LOT_Z

M_PER_LAT = 111_320.0
M_PER_LNG = 111_320.0 * math.cos(math.radians(REF_LAT))

def webots_to_gps(wx: float, wz: float) -> tuple[float, float]:
    dx, dz = wx - REF_WX, wz - REF_WZ
    lat = REF_LAT - dz / M_PER_LAT
    lng = REF_LNG + dx / M_PER_LNG
    return lat, lng

# ── HTTP 유틸 ────────────────────────────────────────────────────────
def _post_json(url: str, data: dict, timeout: float = 3.0) -> dict | None:
    body = json.dumps(data).encode()
    try:
        if _HTTP_LIB == "httpx":
            return httpx.post(url, content=body, headers={"Content-Type": "application/json"}, timeout=timeout).json()
        else:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
    except:
        return None

def _get_json(url: str, timeout: float = 3.0) -> dict | None:
    try:
        if _HTTP_LIB == "httpx":
            return httpx.get(url, timeout=timeout).json()
        else:
            with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=timeout) as r:
                return json.loads(r.read())
    except:
        return None

# ── 백엔드 연동 ──────────────────────────────────────────────────────
def register_with_backend():
    res = _get_json(f"{BACKEND_URL}/")
    if res and res.get("status") == "ok":
        print(f"[백엔드] 연결 확인 (VIN={VIN}, PLATE={PLATE})")

def trigger_lpr():
    def _do():
        global _lpr_triggered, _last_lpr_time
        res = _post_json(
            f"{PMS_URL}/lpr/entry",
            {
                "plate": PLATE,
                "lot_id": LOT_ID,
                "entry_time": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            },
        )
        if res and res.get("pms_session_id"):
            print(f"[LPR] 입차 세션 생성: {res.get('pms_session_id')}")
        else:
            print("[LPR] 입차 트리거 실패 또는 사전 등록 없음")
        _last_lpr_time = time.time()
        _lpr_triggered = True
    threading.Thread(target=_do, daemon=True).start()

def push_sim_location(lat: float, lng: float):
    def _do():
        _post_json(
            f"{BACKEND_URL}/sim/location",
            {
                "lat": lat,
                "lng": lng,
                "speed_kph": DEFAULT_SPEED * 3.6,
                "source": "webots",
            },
            timeout=1.0,
        )
    threading.Thread(target=_do, daemon=True).start()

# ── 차량 구동 ────────────────────────────────────────────────────────
def get_distance_to_parking(gps: GPS) -> float:
    wx, _, wz = gps.getValues()
    return math.sqrt((wx - PARKING_LOT_X)**2 + (wz - PARKING_LOT_Z)**2)

def steer_toward_parking(gps: GPS, left_motor, right_motor):
    wx, _, wz = gps.getValues()
    target_angle = math.atan2(PARKING_LOT_Z - wz, PARKING_LOT_X - wx)
    steer = max(-1.0, min(1.0, 0.5 * target_angle))
    left_motor.setVelocity(DEFAULT_SPEED * (1.0 - steer))
    right_motor.setVelocity(DEFAULT_SPEED * (1.0 + steer))

# ── 메인 ─────────────────────────────────────────────────────────────
robot = Robot()
timestep = int(robot.getBasicTimeStep())

gps = robot.getDevice("gps")
gps.enable(timestep)

try:
    left_motor, right_motor = robot.getDevice("left wheel motor"), robot.getDevice("right wheel motor")
    left_motor.setPosition(float("inf"))
    right_motor.setPosition(float("inf"))
    HAS_MOTORS = True
except:
    HAS_MOTORS = False

threading.Thread(target=register_with_backend, daemon=True).start()
print("[차량] 컨트롤러 시작")

last_gps_send_time = 0.0

while robot.step(timestep) != -1:
    dist = get_distance_to_parking(gps)
    pos = gps.getValues()
    lat, lng = webots_to_gps(pos[0], pos[2])
    now = time.time()

    # 1. 안드로이드 에뮬레이터 GPS 주입 (내비게이션용)
    if now - last_gps_send_time >= 1.0:
        try:
            subprocess.Popen(f"adb emu geo fix {lng} {lat}", shell=True)
            push_sim_location(lat, lng)
            last_gps_send_time = now
        except:
            pass

    # 2. LPR 트리거 (4m 이내)
    if dist <= LPR_THRESHOLD and (now - _last_lpr_time) > _cooldown_s and not _lpr_triggered:
        print(f"[거리: {dist:.1f}m] LPR 인식 트리거")
        trigger_lpr()

    if _lpr_triggered and (now - _last_lpr_time) > _cooldown_s:
        _lpr_triggered = False

    # 3. 모터 구동
    if HAS_MOTORS:
        if dist > 2.0:
            steer_toward_parking(gps, left_motor, right_motor)
        else:
            left_motor.setVelocity(0.0)
            right_motor.setVelocity(0.0)
