"""
CarPayIn 차량 컨트롤러 (Webots 내부 실행)

좌표계: Webots Z-up → translation[X, Y, Z] 에서 X,Y가 수평 평면, Z가 고도
  - ToyotaPrius 시작: (70.7132, 1.04608, -0.173432)
  - 주차장 목표:      (53.33, 3.67, ...)

동작 모드 (WEBOTS_DRIVE_MODE):
  auto   - 60초에 걸쳐 주차장까지 자동 이동 (시각적으로 차량 이동)
  manual - 방향키 / WASD 키보드로 직접 조작
"""
import math, json, os, urllib.request
from datetime import datetime, timezone

# ── Webots 컨트롤러 임포트 ──────────────────────────────────────────────
try:
    from vehicle import Driver
    robot = Driver()
    USING_DRIVER = True
except Exception:
    from controller import Robot
    robot = Robot()
    USING_DRIVER = False

from controller import Keyboard

timestep = int(robot.getBasicTimeStep())

# ── .env 로드 ───────────────────────────────────────────────────────────
_here = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_here, ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _, _v = _line.partition("=")
            _k = _k.strip(); _v = _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
PMS_URL     = os.environ.get("PARKING_PMS_URL", "http://localhost:8001")
PLATE       = os.environ.get("WEBOTS_PLATE", "12가3456")
LOT_ID      = os.environ.get("WEBOTS_LOT_ID", "LOT_TEST_01")
DRIVE_MODE  = os.environ.get("WEBOTS_DRIVE_MODE", "auto").lower()

# ── 좌표 상수 (sim_vehicle.py 와 동일) ─────────────────────────────────
PARKING_LOT_X = 53.33
PARKING_LOT_Y = 3.67
START_X, START_Y = 70.7, 1.0
REF_LAT = 37.48544722
REF_LNG = 127.03636666
M_PER_LAT = 111_320.0
M_PER_LNG = 111_320.0 * math.cos(math.radians(REF_LAT))

def webots_to_gps(wx, wy):
    return (
        REF_LAT + (wy - PARKING_LOT_Y) / M_PER_LAT,
        REF_LNG + (wx - PARKING_LOT_X) / M_PER_LNG,
    )

# ── HTTP 헬퍼 ────────────────────────────────────────────────────────────
def post_json(url, data):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json; charset=utf-8"}
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[VC] POST 실패 {url}: {e}", flush=True)
        return None

# ── GPS 센서 초기화 ──────────────────────────────────────────────────────
gps = robot.getDevice("gps")
if gps:
    gps.enable(timestep)
    print("[VC] GPS 센서 활성화", flush=True)

# ── 키보드 초기화 ────────────────────────────────────────────────────────
keyboard = Keyboard()
keyboard.enable(timestep)

# ── Supervisor: 자신의 translation 필드 참조 ────────────────────────────
self_node = None
translation_field = None
try:
    self_node = robot.getSelf()
    translation_field = self_node.getField("translation")
    cur0 = translation_field.getSFVec3f()
    GROUND_Z = cur0[2]    # 고도 고정값 (-0.173...)
    print(f"[VC] Supervisor 활성 - 초기위치 ({cur0[0]:.2f}, {cur0[1]:.2f}, {cur0[2]:.3f})", flush=True)
except Exception as e:
    GROUND_Z = -0.173432
    print(f"[VC] Supervisor 불가: {e}", flush=True)

# ── 상태 변수 ────────────────────────────────────────────────────────────
lpr_triggered = False
last_lpr_time = 0.0
last_gps_send = 0.0
GPS_INTERVAL_MS = 1000.0

auto_t = 0.0
AUTO_DURATION = 60.0   # 60초에 주차장 도착

current_speed = 0.0
current_steer = 0.0
MAX_SPEED = 20.0
MAX_STEER = 0.4
SPEED_STEP = 2.0
STEER_STEP = 0.5

print(f"[VC] 시작 — mode={DRIVE_MODE}, plate={PLATE}, lot={LOT_ID}", flush=True)

# ════════════════════════════════════════════════════════════════════════
while robot.step(timestep) != -1:
    sim_time = robot.getTime()
    now_ms   = sim_time * 1000.0

    # ── 1. 현재 위치 결정 ────────────────────────────────────────────────
    if DRIVE_MODE == "auto":
        progress = min(auto_t / AUTO_DURATION, 1.0)
        wx = START_X + (PARKING_LOT_X - START_X) * progress
        wy = START_Y + (PARKING_LOT_Y - START_Y) * progress
        spd = max(0.0, 20.0 * (1.0 - progress))

        # 시각적으로 차량 이동 (X, Y 업데이트, Z=고도 유지)
        if translation_field:
            translation_field.setSFVec3f([wx, wy, GROUND_Z])

        auto_t += timestep / 1000.0

        if progress >= 1.0:
            print("[VC] 주차장 도착. 60초 후 재시작", flush=True)
            auto_t = 0.0
            lpr_triggered = False

    else:
        # manual 모드: 실제 GPS 혹은 현재 translation 에서 위치 읽기
        if gps:
            vals = gps.getValues()
            wx, wy = vals[0], vals[1]   # X(동), Y(북) — Z는 고도
        elif translation_field:
            cur = translation_field.getSFVec3f()
            wx, wy = cur[0], cur[1]
        else:
            wx, wy = START_X, START_Y

        spd = abs(current_speed)

        # 키보드 입력
        key = keyboard.getKey()

        if key in (Keyboard.UP, ord('W')):
            current_speed = min(current_speed + SPEED_STEP, MAX_SPEED)
        elif key in (Keyboard.DOWN, ord('S')):
            current_speed = max(current_speed - SPEED_STEP, -MAX_SPEED * 0.3)
        else:
            current_speed = 0.0 if abs(current_speed) < 1.0 else current_speed * 0.8

        if key in (Keyboard.LEFT, ord('A')):
            current_steer = max(current_steer - STEER_STEP, -MAX_STEER)
        elif key in (Keyboard.RIGHT, ord('D')):
            current_steer = min(current_steer + STEER_STEP, MAX_STEER)
        else:
            current_steer = 0.0 if abs(current_steer) < 0.01 else current_steer * 0.7

        if USING_DRIVER:
            robot.setCruisingSpeed(current_speed)
            robot.setSteeringAngle(current_steer)

    # ── 2. 주차장까지 거리 계산 ──────────────────────────────────────────
    dist = math.sqrt((wx - PARKING_LOT_X) ** 2 + (wy - PARKING_LOT_Y) ** 2)

    # ── 3. 위치 → backend 전송 (1초 간격) ────────────────────────────────
    if now_ms - last_gps_send >= GPS_INTERVAL_MS:
        last_gps_send = now_ms
        lat, lng = webots_to_gps(wx, wy)
        post_json(f"{BACKEND_URL}/sim/location", {
            "lat": lat, "lng": lng,
            "speed_kph": round(spd, 1),
            "heading": 225.0,
            "source": "webots_controller",
        })
        print(f"[GPS] wx={wx:.2f} wy={wy:.2f} dist={dist:.1f}m", flush=True)

    # ── 4. LPR 트리거 (4m 이내, 30초 쿨다운) ────────────────────────────
    if dist <= 4.0 and not lpr_triggered and (sim_time - last_lpr_time) > 30.0:
        entry_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        print(f"[LPR] 진입 감지! dist={dist:.1f}m plate={PLATE}", flush=True)
        res = post_json(f"{PMS_URL}/lpr/entry", {
            "plate": PLATE,
            "lot_id": LOT_ID,
            "entry_time": entry_time,
        })
        print(f"[LPR] 응답: {res}", flush=True)
        lpr_triggered = True
        last_lpr_time = sim_time
