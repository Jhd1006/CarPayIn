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

# 에뮬레이터가 다른 PC에 있을 때: ADB_HOST에 노트북 IP 입력
# 비어 있으면 로컬 ADB 사용
ADB_HOST     = get_config("ADB_HOST", "")
ADB_PORT     = get_config("ADB_PORT", "5037")

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

def steer_toward_parking(gps: GPS, left_steer, right_steer, left_wheel, right_wheel):
    wx, _, wz = gps.getValues()
    # 현재 진행 방향 기준 목표 각도 계산
    dx = PARKING_LOT_X - wx
    dz = PARKING_LOT_Z - wz
    target_angle = math.atan2(dx, dz)
    steer_angle = max(-0.5, min(0.5, 0.8 * target_angle))
    left_steer.setPosition(steer_angle)
    right_steer.setPosition(steer_angle)
    left_wheel.setVelocity(DEFAULT_SPEED)
    right_wheel.setVelocity(DEFAULT_SPEED)

# ── 메인 ─────────────────────────────────────────────────────────────
robot = Robot()
timestep = int(robot.getBasicTimeStep())

gps = robot.getDevice("gps")
gps.enable(timestep)

try:
    left_steer  = robot.getDevice("left_steer")
    right_steer = robot.getDevice("right_steer")
    left_wheel  = robot.getDevice("left_front_wheel")
    right_wheel = robot.getDevice("right_front_wheel")
    left_steer.setPosition(0.0)
    right_steer.setPosition(0.0)
    left_wheel.setPosition(float("inf"))
    right_wheel.setPosition(float("inf"))
    left_wheel.setVelocity(0.0)
    right_wheel.setVelocity(0.0)
    HAS_MOTORS = True
except Exception as e:
    print(f"[경고] 모터 초기화 실패: {e}")
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
            adb_cmd = f"adb -H {ADB_HOST} -P {ADB_PORT} emu geo fix {lng} {lat}" if ADB_HOST else f"adb emu geo fix {lng} {lat}"
            result = subprocess.run(adb_cmd, shell=True, capture_output=True, text=True, timeout=3)
            if result.returncode != 0:
                print(f"[ADB 오류] {result.stderr.strip()}")
            else:
                print(f"[GPS] lat={lat:.6f} lng={lng:.6f}")
            push_sim_location(lat, lng)
            last_gps_send_time = now
        except Exception as e:
            print(f"[ADB 예외] {e}")

    # 2. LPR 트리거 (4m 이내)
    if dist <= LPR_THRESHOLD and (now - _last_lpr_time) > _cooldown_s and not _lpr_triggered:
        print(f"[거리: {dist:.1f}m] LPR 인식 트리거")
        trigger_lpr()

    if _lpr_triggered and (now - _last_lpr_time) > _cooldown_s:
        _lpr_triggered = False

    # 3. 모터 구동 비활성화 — 수동 조작 모드
    # (자동 주행이 필요하면 아래 주석 해제)
    # if HAS_MOTORS:
    #     if dist > 2.0:
    #         steer_toward_parking(gps, left_steer, right_steer, left_wheel, right_wheel)
    #     else:
    #         left_wheel.setVelocity(0.0)
    #         right_wheel.setVelocity(0.0)
