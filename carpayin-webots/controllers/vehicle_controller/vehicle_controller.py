"""
CarPayIn 차량 컨트롤러 - 물리 기반 자율주행

Phase 순서:
  approaching_entry → 입차 차단기 앞까지 주행 후 정차
  at_entry_gate     → LPR 입차 트리거 + 차단기 열림 대기
  entering          → 차단기 통과 후 주차장 내부 진입
  parking           → 주차 지점까지 주행 후 정차
  at_parking        → PMS 결제 완료 폴링 (5초 간격)
  uturn             → U턴 루프 (서 → 북 → 동)
  to_exit           → 출구 차선 합류
  approaching_exit  → 출차 차단기 앞까지 주행 후 정차
  at_exit_gate      → LPR 출차 트리거 + 차단기 열림 대기 (미결제 시 재시도)
  exiting           → 차단기 통과 후 출차 완료
  done              → 정지

좌표 기준 (Car Pay-in.wbt):
  입차 차단기: Robot(9.08, 13.29) + Solid(40.70, -11.63) = world (49.78, 1.65)
  출차 차단기: Robot(9.03, 11.94) + Solid(40.70, -11.63) = world (49.73, 0.31)
  주차 지점:   PARKING_SPOT Pose (13.14, -7.04)
  차량 시작:   ToyotaPrius (70.71, 1.05)
"""
import math
import json
import os
import urllib.request
from datetime import datetime, timezone

# ── Webots 드라이버 임포트 ──────────────────────────────────────────────
try:
    from vehicle import Driver
    robot = Driver()
    USING_DRIVER = True
except Exception:
    from controller import Robot
    robot = Robot()
    USING_DRIVER = False

timestep = int(robot.getBasicTimeStep())


def step_robot():
    return robot.step() if USING_DRIVER else robot.step(timestep)


# ── .env 로드 ────────────────────────────────────────────────────────────
_here = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_here, ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _, _v = _line.partition("=")
            _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v

PMS_URL = os.environ.get("PARKING_PMS_URL", "http://localhost:8001")
PLATE   = os.environ.get("WEBOTS_PLATE",    "12가3456")
LOT_ID  = os.environ.get("WEBOTS_LOT_ID",   "LOT_TEST_01")

ENTRY_BARRIER_PORT = 8100
EXIT_BARRIER_PORT  = 8101

# ── 웨이포인트 정의 (x, y, target_speed_kmh) ─────────────────────────────
# 차단기 Y 좌표
_ENTRY_Y = 1.65
_EXIT_Y  = 0.31

WP = {
    # 입차 차단기 앞 정차 지점 (X=53.5: 차단기 X=49.78 기준 약 4m 앞)
    "approaching_entry": [
        (53.5,   _ENTRY_Y,  10.0),
    ],
    # 차단기 통과 → 주차장 내부
    "entering": [
        (47.0,   _ENTRY_Y,  10.0),
        (28.0,   _ENTRY_Y,  15.0),
    ],
    # 주차 지점 (13.14, -7.04) 까지
    "parking": [
        (20.0,    1.0,      10.0),
        (20.0,   -6.0,       8.0),
        (13.0,   -7.0,       5.0),
    ],
    # U턴: 서 → 북 방향 루프
    "uturn": [
        ( 7.0,   -7.0,       8.0),
        ( 7.0,    2.0,      10.0),
    ],
    # 출구 차선 합류
    "to_exit": [
        (20.0,    0.5,      12.0),
        (37.0,   _EXIT_Y,  12.0),
    ],
    # 출차 차단기 앞 정차 지점 (X=47.5: 차단기 X=49.73 기준 약 2m 앞)
    "approaching_exit": [
        (47.5,   _EXIT_Y,    8.0),
    ],
    # 차단기 통과 → 출차 완료
    "exiting": [
        (57.0,   _EXIT_Y,   12.0),
        (74.0,   _EXIT_Y,   10.0),
    ],
}

# 단계 순서 (주행 단계와 특수 대기 단계 교대)
STATE_SEQUENCE = [
    "approaching_entry",
    "at_entry_gate",
    "entering",
    "parking",
    "at_parking",
    "uturn",
    "to_exit",
    "approaching_exit",
    "at_exit_gate",
    "exiting",
    "done",
]

# 도달 판정 거리
ARRIVE_STOP = 2.5   # m — 정차 직전 마지막 웨이포인트
ARRIVE_PASS = 5.0   # m — 통과용 중간 웨이포인트

# 속도/조향 파라미터
SLOW_RADIUS = 8.0   # m — 이 거리부터 감속
MIN_SPEED   = 2.0   # km/h — 최저 속도
KP_STEER    = 1.2   # 조향 P 게인
MAX_STEER   = 0.4   # rad

# 타임아웃
ENTRY_BARRIER_TIMEOUT = 15.0   # s
EXIT_BARRIER_TIMEOUT  = 15.0   # s
EXIT_RETRY_INTERVAL   = 8.0    # s — 미결제 재시도 간격
PARK_POLL_INTERVAL    = 5.0    # s — PMS 결제 상태 폴링 간격
BARRIER_POLL_INTERVAL = 0.5    # s — 차단기 상태 폴링 간격


# ── HTTP 헬퍼 ────────────────────────────────────────────────────────────
def _get(url, timeout=3):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[VC] GET {url}: {e}", flush=True)
        return None


def _post(url, data, timeout=10):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json; charset=utf-8"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[VC] POST {url}: {e}", flush=True)
        return None


def is_barrier_open(port):
    data = _get(f"http://localhost:{port}/status")
    return bool(data and data.get("is_open"))


def get_pms_status():
    data = _get(f"{PMS_URL}/parking/session-status?plate={PLATE}&lot_id={LOT_ID}")
    return data.get("status") if data else None


def trigger_entry():
    t = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    print(f"[LPR] 입차 → plate={PLATE}", flush=True)
    res = _post(f"{PMS_URL}/lpr/entry", {"plate": PLATE, "lot_id": LOT_ID, "entry_time": t})
    print(f"[LPR] 입차 응답: {res}", flush=True)
    return res


def trigger_exit():
    print(f"[LPR] 출차 → plate={PLATE}", flush=True)
    res = _post(f"{PMS_URL}/lpr/exit", {"plate": PLATE, "lot_id": LOT_ID})
    print(f"[LPR] 출차 응답: {res}", flush=True)
    return res


# ── 조향/속도 계산 ────────────────────────────────────────────────────────
def compute_steer(wx, wy, tx, ty, heading):
    bearing = math.atan2(ty - wy, tx - wx)
    err = bearing - heading
    err = (err + math.pi) % (2 * math.pi) - math.pi
    return max(-MAX_STEER, min(MAX_STEER, KP_STEER * err))


def approach_speed(dist, target_speed):
    if dist > SLOW_RADIUS:
        return target_speed
    return max(MIN_SPEED, target_speed * dist / SLOW_RADIUS)


def drive(speed, steer):
    if USING_DRIVER:
        robot.setCruisingSpeed(speed)
        robot.setSteeringAngle(steer)


def stop():
    drive(0, 0)


# ── 센서 초기화 ───────────────────────────────────────────────────────────
gps = robot.getDevice("gps")
if gps:
    gps.enable(timestep)

translation_field = None
GROUND_Z = -0.173432
try:
    self_node = robot.getSelf()
    translation_field = self_node.getField("translation")
    GROUND_Z = translation_field.getSFVec3f()[2]
except Exception as e:
    print(f"[VC] Supervisor 불가: {e}", flush=True)

# ── 상태 초기화 ───────────────────────────────────────────────────────────
state_idx = 0
state     = STATE_SEQUENCE[0]
wp_idx    = 0

# GPS 기반 헤딩 추정 (초기: 차단기 방향인 -X)
heading  = math.pi
prev_wx  = 70.7
prev_wy  = 1.05
wx, wy   = prev_wx, prev_wy

# at_entry_gate
entry_lpr_sent   = False
entry_wait_t     = 0.0
entry_poll_t     = 0.0

# at_parking
park_poll_t      = 0.0

# at_exit_gate
exit_lpr_sent    = False
exit_lpr_res     = None
exit_wait_t      = 0.0
exit_poll_t      = 0.0
exit_retry_t     = 0.0


def advance_state():
    global state_idx, state, wp_idx
    global entry_lpr_sent, entry_wait_t, entry_poll_t
    global park_poll_t
    global exit_lpr_sent, exit_lpr_res, exit_wait_t, exit_poll_t, exit_retry_t

    state_idx += 1
    state     = STATE_SEQUENCE[min(state_idx, len(STATE_SEQUENCE) - 1)]
    wp_idx    = 0

    entry_lpr_sent = False
    entry_wait_t = entry_poll_t = 0.0
    park_poll_t  = 0.0
    exit_lpr_sent = False
    exit_lpr_res  = None
    exit_wait_t = exit_poll_t = exit_retry_t = 0.0

    print(f"[VC] ── {state} ──", flush=True)


print(f"[VC] 시작 — plate={PLATE}, lot={LOT_ID}, PMS={PMS_URL}", flush=True)
print(f"[VC] 모드: 물리 기반 자율주행", flush=True)
print(f"[VC] ── {state} ──", flush=True)

# ════════════════════════════════════════════════════════════════════════
while step_robot() != -1:
    dt = timestep / 1000.0

    # ── GPS 위치 + 헤딩 갱신 ─────────────────────────────────────────────
    if gps:
        vals = gps.getValues()
        wx, wy = vals[0], vals[1]
    elif translation_field:
        cur = translation_field.getSFVec3f()
        wx, wy = cur[0], cur[1]

    moved = math.sqrt((wx - prev_wx) ** 2 + (wy - prev_wy) ** 2)
    if moved > 0.12:
        heading = math.atan2(wy - prev_wy, wx - prev_wx)
        prev_wx, prev_wy = wx, wy

    # ════════════════════════════════════════════════════════════════════
    # 주행 단계 — 웨이포인트 추종
    # ════════════════════════════════════════════════════════════════════
    if state in WP:
        wps = WP[state]
        if wp_idx >= len(wps):
            stop()
            advance_state()
            continue

        tx, ty, tspeed = wps[wp_idx]
        dist    = math.sqrt((wx - tx) ** 2 + (wy - ty) ** 2)
        is_last = (wp_idx == len(wps) - 1)
        thresh  = ARRIVE_STOP if is_last else ARRIVE_PASS

        if dist < thresh:
            if is_last:
                stop()
                advance_state()
            else:
                wp_idx += 1
        else:
            steer = compute_steer(wx, wy, tx, ty, heading)
            speed = approach_speed(dist, tspeed) if is_last else tspeed
            drive(speed, steer)

    # ════════════════════════════════════════════════════════════════════
    # at_entry_gate — LPR 입차 + 차단기 열림 대기
    # ════════════════════════════════════════════════════════════════════
    elif state == "at_entry_gate":
        if not entry_lpr_sent:
            trigger_entry()
            entry_lpr_sent = True
            print("[VC] 입차 차단기 열림 대기…", flush=True)

        entry_wait_t += dt

        if entry_wait_t >= 2.0:   # 최소 2초 대기 후 폴링 시작
            entry_poll_t += dt
            if entry_poll_t >= BARRIER_POLL_INTERVAL:
                entry_poll_t = 0.0
                if is_barrier_open(ENTRY_BARRIER_PORT):
                    print("[VC] 입차 차단기 열림 확인 → 통과 시작", flush=True)
                    advance_state()

        if entry_wait_t >= ENTRY_BARRIER_TIMEOUT:
            print("[VC] 입차 차단기 타임아웃 → 강제 통과", flush=True)
            advance_state()

    # ════════════════════════════════════════════════════════════════════
    # at_parking — PMS 결제 완료 폴링
    # ════════════════════════════════════════════════════════════════════
    elif state == "at_parking":
        park_poll_t += dt
        if park_poll_t >= PARK_POLL_INTERVAL:
            park_poll_t = 0.0
            status = get_pms_status()
            print(f"[VC] PMS 세션 상태: {status}", flush=True)
            if status == "paid":
                print("[VC] 결제 완료! 출차 시작", flush=True)
                advance_state()

    # ════════════════════════════════════════════════════════════════════
    # at_exit_gate — LPR 출차 + 차단기 열림 대기 (미결제 시 재시도)
    # ════════════════════════════════════════════════════════════════════
    elif state == "at_exit_gate":
        if not exit_lpr_sent:
            exit_lpr_res  = trigger_exit()
            exit_lpr_sent = True
            exit_wait_t   = 0.0
            exit_retry_t  = 0.0

        status = exit_lpr_res.get("status") if exit_lpr_res else None

        if status == "opened":
            exit_wait_t += dt
            exit_poll_t += dt
            if exit_wait_t >= 2.0 and exit_poll_t >= BARRIER_POLL_INTERVAL:
                exit_poll_t = 0.0
                if is_barrier_open(EXIT_BARRIER_PORT):
                    print("[VC] 출차 차단기 열림 확인 → 출차 시작", flush=True)
                    advance_state()
            if exit_wait_t >= EXIT_BARRIER_TIMEOUT:
                print("[VC] 출차 차단기 타임아웃 → 강제 출차", flush=True)
                advance_state()

        elif status in ("not_paid", "not_found", None):
            exit_retry_t += dt
            if exit_retry_t >= EXIT_RETRY_INTERVAL:
                print("[VC] 미결제 또는 오류 → 출차 재시도", flush=True)
                exit_lpr_res  = trigger_exit()
                exit_lpr_sent = True
                exit_wait_t   = 0.0
                exit_retry_t  = 0.0

    # ════════════════════════════════════════════════════════════════════
    # done
    # ════════════════════════════════════════════════════════════════════
    elif state == "done":
        stop()
