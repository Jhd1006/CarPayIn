"""
vehicle_controller.py – Webots 차량 컨트롤러
차량 물리 시뮬레이션 + 위치/속도 백엔드 전달 (VHAL 대역)
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

SERVER_DIR = pathlib.Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
from shared_config import get_config

PATCH_VERSION = "CARPAYIN_WEBOTS_BRIDGE_20260609_SIM_VHAL"

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

PLATE  = get_config("WEBOTS_PLATE", "123가4567")
LOT_ID = get_config("WEBOTS_LOT_ID", "LOT_TEST_01")

# 주차장 위치 (Webots 월드 좌표, 미터)
PARKING_LOT_X, PARKING_LOT_Y = 53.33, 3.67

# LPR 트리거 거리 (m)
LPR_THRESHOLD = 4.0

DEFAULT_SPEED = 5.0
DRIVE_MODE    = get_config("WEBOTS_DRIVE_MODE", "manual").lower()

# GPS 좌표 변환 기준점 (Webots 월드 원점 → 실제 위경도)
REF_LAT, REF_LNG = 37.48544722, 127.03636666
REF_WX,  REF_WY  = PARKING_LOT_X, PARKING_LOT_Y
M_PER_LAT = 111_320.0
M_PER_LNG = 111_320.0 * math.cos(math.radians(REF_LAT))

# ── 상태 변수 ────────────────────────────────────────────────────────
_lpr_triggered  = False
_last_lpr_time  = 0.0
_lpr_cooldown_s = 30.0

_prev_wx, _prev_wy = 0.0, 0.0   # 이전 프레임 위치 (heading 계산용)
_current_speed_kph = 0.0

# ── 좌표 변환 ────────────────────────────────────────────────────────
def webots_to_gps(wx: float, wy: float) -> tuple[float, float]:
    """Webots 월드 좌표(m) → 위경도"""
    dx, dy = wx - REF_WX, wy - REF_WY
    return REF_LAT + dy / M_PER_LAT, REF_LNG + dx / M_PER_LNG

def calc_heading(dx: float, dy: float) -> float:
    """이동 벡터 → 진북 기준 방위각(도)"""
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return 0.0
    angle = math.degrees(math.atan2(dx, dy))   # 북=0, 동=90
    return angle % 360.0

# ── HTTP 유틸 ────────────────────────────────────────────────────────
def _post_json(url: str, data: dict, timeout: float = 3.0) -> dict | None:
    body = json.dumps(data).encode()
    try:
        if _HTTP_LIB == "httpx":
            return httpx.post(url, content=body,
                              headers={"Content-Type": "application/json"},
                              timeout=timeout).json()
        else:
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json"},
                                         method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
    except:
        return None

def _get_json(url: str, timeout: float = 3.0) -> dict | None:
    try:
        if _HTTP_LIB == "httpx":
            return httpx.get(url, timeout=timeout).json()
        else:
            with urllib.request.urlopen(
                    urllib.request.Request(url, method="GET"), timeout=timeout) as r:
                return json.loads(r.read())
    except:
        return None

# ── 백엔드 연동 ──────────────────────────────────────────────────────
def check_backend():
    res = _get_json(f"{BACKEND_URL}/health")
    if res and res.get("status") == "ok":
        log(f"[백엔드] 연결 확인")

def push_sim_location(lat: float, lng: float, speed_kph: float, heading: float):
    """차량 상태를 백엔드에 전달 — 앱이 이걸 폴링해서 지오펜스 판단"""
    def _do():
        _post_json(
            f"{BACKEND_URL}/sim/location",
            {"lat": lat, "lng": lng, "speed_kph": speed_kph,
             "heading": heading, "source": "webots"},
            timeout=1.0,
        )
    threading.Thread(target=_do, daemon=True).start()

def trigger_lpr():
    """LPR 인식 시뮬레이션 — 차량이 입구 4m 이내 진입 시 PMS로 번호판 전송"""
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

# ── 차량 구동 ────────────────────────────────────────────────────────
def get_distance_to_parking(gps: GPS) -> float:
    wx, wy, _ = gps.getValues()
    return math.sqrt((wx - PARKING_LOT_X) ** 2 + (wy - PARKING_LOT_Y) ** 2)

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

# ── 초기화 ───────────────────────────────────────────────────────────
robot    = Driver() if Driver is not None else Robot()
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

threading.Thread(target=check_backend, daemon=True).start()
log(f"[CARPAYIN] {PATCH_VERSION} loaded")
log(f"[차량] 주행 모드: {DRIVE_MODE}  |  LPR 거리: {LPR_THRESHOLD}m")
set_driver_motion(0.0, 0.0)

last_location_push = 0.0

# ── 메인 루프 ────────────────────────────────────────────────────────
while robot.step(timestep) != -1:
    wx, wy, _ = gps.getValues()
    dist = math.sqrt((wx - PARKING_LOT_X) ** 2 + (wy - PARKING_LOT_Y) ** 2)
    lat, lng = webots_to_gps(wx, wy)
    now = time.time()

    # 1. 차량 상태 → 백엔드 push (1초마다)
    #    앱이 이걸 폴링해서 지오펜스 / 사전등록 판단 (VHAL 대역)
    if now - last_location_push >= 1.0:
        dx, dy = wx - _prev_wx, wy - _prev_wy
        _current_speed_kph = math.sqrt(dx**2 + dy**2) / max(now - last_location_push, 0.001) * 3.6
        heading = calc_heading(dx, dy)
        push_sim_location(lat, lng, _current_speed_kph, heading)
        _prev_wx, _prev_wy = wx, wy
        last_location_push = now
        log(f"[GPS] lat={lat:.6f} lng={lng:.6f} speed={_current_speed_kph:.1f}km/h dist={dist:.1f}m")

    # 2. LPR 트리거 (4m 이내) — 차량 물리 위치 기반
    if (dist <= LPR_THRESHOLD
            and not _lpr_triggered
            and (now - _last_lpr_time) > _lpr_cooldown_s):
        log(f"[거리: {dist:.1f}m] LPR 인식 트리거")
        trigger_lpr()

    if dist > LPR_THRESHOLD * 2 and (now - _last_lpr_time) > _lpr_cooldown_s:
        _lpr_triggered = False

    # 3. 주행 제어
    key   = keyboard.getKey()
    speed = 0.0
    steer = 0.0
    if DRIVE_MODE == "auto":
        if dist > 2.0:
            dx_park = PARKING_LOT_X - wx
            dy_park = PARKING_LOT_Y - wy
            steer = max(-0.5, min(0.5, 0.8 * math.atan2(dx_park, dy_park)))
            speed = DEFAULT_SPEED
    elif DRIVE_MODE == "manual":
        if key == keyboard.UP:
            speed = DEFAULT_SPEED
        elif key == keyboard.DOWN:
            speed = -DEFAULT_SPEED
        if key in (keyboard.LEFT,
                   keyboard.UP + keyboard.LEFT,
                   keyboard.DOWN + keyboard.LEFT):
            steer = -0.3
        elif key in (keyboard.RIGHT,
                     keyboard.UP + keyboard.RIGHT,
                     keyboard.DOWN + keyboard.RIGHT):
            steer = 0.3
    elif DRIVE_MODE != "gps-only":
        log(f"[경고] 알 수 없는 WEBOTS_DRIVE_MODE={DRIVE_MODE}")

    set_driver_motion(speed, steer)
