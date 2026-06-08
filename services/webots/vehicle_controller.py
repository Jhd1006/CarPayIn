"""
vehicle_controller.py – Webots 차량 컨트롤러 (Android 내비게이션 연동)
"""

from controller import Robot, GPS
try:
    from vehicle import Driver
except ImportError:
    Driver = None
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

PATCH_VERSION = "CARPAYIN_WEBOTS_BRIDGE_20260605_STOP_SAFE"

def log(message: str):
    print(message, flush=True)

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

# 에뮬레이터가 다른 PC에 있을 때: GPS_PROXY_URL 또는 ADB_HOST에 노트북 IP 입력
# 비어 있으면 Webots PC의 로컬 ADB를 직접 사용
GPS_PROXY_URL = get_config("GPS_PROXY_URL", "")
ADB_HOST      = get_config("ADB_HOST", "")
ADB_TARGET    = get_config("ADB_TARGET", "")
ADB_PORT      = get_config("ADB_PORT", "5037")

PARKING_LOT_X, PARKING_LOT_Y = 53.33, 3.67
LPR_THRESHOLD        = 4.0
DEFAULT_SPEED        = 5.0
DEFAULT_SPEED_KPH    = DEFAULT_SPEED * 3.6
DRIVE_MODE           = get_config("WEBOTS_DRIVE_MODE", "manual").lower()

# ── 상태 변수 ────────────────────────────────────────────────────────
_lpr_triggered     = False
_last_lpr_time     = 0.0
_cooldown_s        = 30.0

# ── GPS 좌표 변환 ────────────────────────────────────────────────────
REF_LAT, REF_LNG = 37.48544722, 127.03636666
REF_WX, REF_WY   = PARKING_LOT_X, PARKING_LOT_Y

M_PER_LAT = 111_320.0
M_PER_LNG = 111_320.0 * math.cos(math.radians(REF_LAT))

def webots_to_gps(wx: float, wy: float) -> tuple[float, float]:
    dx, dy = wx - REF_WX, wy - REF_WY
    lat = REF_LAT + dy / M_PER_LAT
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
        log(f"[백엔드] 연결 확인 (VIN={VIN}, PLATE={PLATE})")

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
            log(f"[LPR] 입차 세션 생성: {res.get('pms_session_id')}")
        else:
            log("[LPR] 입차 트리거 실패 또는 사전 등록 없음")
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
                "speed_kph": DEFAULT_SPEED_KPH,
                "source": "webots",
            },
            timeout=1.0,
        )
    threading.Thread(target=_do, daemon=True).start()

def get_gps_proxy_url() -> str:
    if GPS_PROXY_URL:
        return GPS_PROXY_URL.rstrip("/")
    if ADB_HOST:
        host = ADB_HOST.split(":", 1)[0]
        return f"http://{host}:5600"
    if ADB_TARGET:
        host = ADB_TARGET.split(":", 1)[0]
        return f"http://{host}:5600"
    return ""

# ── 차량 구동 ────────────────────────────────────────────────────────
def get_distance_to_parking(gps: GPS) -> float:
    wx, wy, _ = gps.getValues()
    return math.sqrt((wx - PARKING_LOT_X)**2 + (wy - PARKING_LOT_Y)**2)

def steer_toward_parking(gps: GPS, left_steer, right_steer, left_wheel, right_wheel):
    wx, wy, _ = gps.getValues()
    # 현재 진행 방향 기준 목표 각도 계산
    dx = PARKING_LOT_X - wx
    dy = PARKING_LOT_Y - wy
    target_angle = math.atan2(dx, dy)
    steer_angle = max(-0.5, min(0.5, 0.8 * target_angle))
    left_steer.setPosition(steer_angle)
    right_steer.setPosition(steer_angle)
    left_wheel.setVelocity(DEFAULT_SPEED)
    right_wheel.setVelocity(DEFAULT_SPEED)

def set_driver_motion(speed_mps: float, steer: float):
    if HAS_DRIVER:
        robot.setSteeringAngle(-steer)
        if hasattr(robot, "setBrakeIntensity"):
            robot.setBrakeIntensity(1.0 if speed_mps == 0.0 else 0.0)
        robot.setCruisingSpeed(speed_mps * 3.6)
    elif HAS_MOTORS:
        left_steer.setPosition(steer)
        right_steer.setPosition(steer)
        left_wheel.setVelocity(speed_mps)
        right_wheel.setVelocity(speed_mps)

# ── 메인 ─────────────────────────────────────────────────────────────
robot = Driver() if Driver is not None else Robot()
timestep = int(robot.getBasicTimeStep())
HAS_DRIVER = Driver is not None

gps = robot.getDevice("gps")
gps.enable(timestep)

keyboard = robot.getKeyboard()
keyboard.enable(timestep)

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
    HAS_MOTORS = not HAS_DRIVER
except Exception as e:
    log(f"[경고] 모터 초기화 실패: {e}")
    HAS_MOTORS = False

threading.Thread(target=register_with_backend, daemon=True).start()
log(f"[CARPAYIN] {PATCH_VERSION} loaded")
log("[차량] 컨트롤러 시작")
log(f"[차량] 주행 모드: {DRIVE_MODE} (manual: 방향키, auto: 주차장 자동 이동, gps-only: 이동 없음)")
set_driver_motion(0.0, 0.0)

last_gps_send_time = 0.0

while robot.step(timestep) != -1:
    dist = get_distance_to_parking(gps)
    pos = gps.getValues()
    lat, lng = webots_to_gps(pos[0], pos[1])
    now = time.time()

    # 1. 안드로이드 에뮬레이터 GPS 주입 (내비게이션용)
    if now - last_gps_send_time >= 1.0:
        try:
            gps_proxy_url = get_gps_proxy_url()
            if gps_proxy_url:
                # 노트북의 GPS 프록시 서버로 전송 (프록시가 adb emu geo fix 실행)
                _post_json(gps_proxy_url, {"lat": lat, "lng": lng})
            else:
                subprocess.Popen(f"adb emu geo fix {lng} {lat}", shell=True)
            log(f"[GPS] lat={lat:.6f} lng={lng:.6f}")
            push_sim_location(lat, lng)
            last_gps_send_time = now
        except Exception as e:
            log(f"[GPS 오류] {e}")

    # 2. LPR 트리거 (4m 이내)
    if dist <= LPR_THRESHOLD and (now - _last_lpr_time) > _cooldown_s and not _lpr_triggered:
        log(f"[거리: {dist:.1f}m] LPR 인식 트리거")
        trigger_lpr()

    if _lpr_triggered and (now - _last_lpr_time) > _cooldown_s:
        _lpr_triggered = False

    # 3. 주행 제어
    key = keyboard.getKey()
    speed = 0.0
    steer = 0.0
    if DRIVE_MODE == "auto":
        if dist > 2.0:
            wx, wy, _ = gps.getValues()
            dx = PARKING_LOT_X - wx
            dy = PARKING_LOT_Y - wy
            steer = max(-0.5, min(0.5, 0.8 * math.atan2(dx, dy)))
            speed = DEFAULT_SPEED
    elif DRIVE_MODE == "manual":
        if key == keyboard.UP:
            speed = DEFAULT_SPEED
        elif key == keyboard.DOWN:
            speed = -DEFAULT_SPEED
        if key == keyboard.LEFT or key == (keyboard.UP + keyboard.LEFT) or key == (keyboard.DOWN + keyboard.LEFT):
            steer = -0.3
        elif key == keyboard.RIGHT or key == (keyboard.UP + keyboard.RIGHT) or key == (keyboard.DOWN + keyboard.RIGHT):
            steer = 0.3
    elif DRIVE_MODE != "gps-only":
        log(f"[경고] 알 수 없는 WEBOTS_DRIVE_MODE={DRIVE_MODE}, 정지 유지")

    set_driver_motion(speed, steer)
