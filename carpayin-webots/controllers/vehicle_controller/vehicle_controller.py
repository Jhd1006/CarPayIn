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
import urllib.parse
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
PLATE   = os.environ.get("WEBOTS_PLATE",    "123가4567")
LOT_ID  = os.environ.get("WEBOTS_LOT_ID",   "LOT_GANGNAM_01")

ENTRY_BARRIER_PORT = 8100
EXIT_BARRIER_PORT  = 8101

# 차단기 Y 좌표
_ENTRY_Y = 1.65
_EXIT_Y  = 0.31
_PARK_Y  = -3.0   # 주차 차로 Y: 걸림 없는 범위

WP = {
    # 1. 입차 차단기 앞 정차 (X=53.5, 차단기 X=49.78 기준 약 3.7m 앞)
    "approaching_entry": [
        (53.5, _ENTRY_Y, 8.0),
    ],
    # 2. 차단기 통과 후 주차장 직진
    "entering": [
        (47.0, _ENTRY_Y, 8.0),
        (25.0, _ENTRY_Y, 8.0),
    ],
    # 3. 주차장 서쪽 끝까지 직진 (Y 고정)
    "parking": [
        (5.0, _ENTRY_Y, 6.0),
    ],
    # 4. 크게 U턴: 남쪽 하강 → 동쪽 이동 → 북쪽 상승 → 출구 차선 합류
    "uturn": [
        ( 5.0, -8.0, 5.0),   # 서쪽 끝에서 남쪽으로 꺾기
        (20.0, -8.0, 6.0),   # 남쪽 차선 동쪽으로 이동
        (20.0, _EXIT_Y, 5.0),# 출구 차선(Y=0.31) 까지 북쪽으로
    ],
    # 5. 출구 방향 직진 → 센서 이전 정차 (차단기 X=49.73 기준 6.7m 앞)
    "to_exit": [
        (38.0, _EXIT_Y, 8.0),
        (43.0, _EXIT_Y, 7.0),
    ],
    # 6. 결제 후 차단기 접근
    "approaching_exit": [
        (47.5, _EXIT_Y, 6.0),
    ],
    # 7. 출차
    "exiting": [
        (57.0, _EXIT_Y, 10.0),
        (74.0, _EXIT_Y, 10.0),
    ],
}

# 단계 순서 (주행 단계와 특수 대기 단계 교대)
STATE_SEQUENCE = [
    "approaching_entry",
    "at_entry_gate",
    "entering",
    "parking",
    "uturn",
    "to_exit",
    "at_parking",        # 출구 차단기 센서 이전 정차, 결제 완료 대기
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
MIN_SPEED   = 4.0   # km/h — 최저 속도
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
    query = urllib.parse.urlencode({"plate": PLATE, "lot_id": LOT_ID})
    data = _get(f"{PMS_URL}/parking/session-status?{query}")
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
    return max(-MAX_STEER, min(MAX_STEER, -KP_STEER * err))


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
rotation_field = None
GROUND_Z = -0.173432
try:
    self_node = robot.getSelf()
    translation_field = self_node.getField("translation")
    rotation_field = self_node.getField("rotation")
    GROUND_Z = translation_field.getSFVec3f()[2]
except Exception as e:
    print(f"[VC] Supervisor 불가: {e}", flush=True)

# ── 상태 초기화 ───────────────────────────────────────────────────────────
state_idx = 0
state     = STATE_SEQUENCE[0]
wp_idx    = 0

# GPS 기반 헤딩 추정 (초기: 차단기 방향인 -X)
heading  = math.pi
prev_wx  = 53.5
prev_wy  = 1.65
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

    if rotation_field:
        rot = rotation_field.getSFRotation()
        heading = rot[3] * (1.0 if rot[2] >= 0 else -1.0)
    else:
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
            print(f"[POS] ({wx:.1f},{wy:.1f}) hdg={math.degrees(heading):.0f}° → ({tx},{ty}) dist={dist:.1f}m [{state}]", flush=True)

    # ════════════════════════════════════════════════════════════════════
    # at_entry_gate — LPR 입차 + 차단기 열림 대기
    # ════════════════════════════════════════════════════════════════════
    elif state == "at_entry_gate":
        if not entry_lpr_sent:
            res = trigger_entry()
            entry_lpr_sent = True
            lpr_status = res.get("status") if res else None
            if lpr_status in ("created", "existing"):
                print(f"[VC] 입차 승인({lpr_status}) → 차단기 열기", flush=True)
                _post(f"http://localhost:{ENTRY_BARRIER_PORT}/open", {})
            else:
                print(f"[VC] 입차 LPR 응답: {lpr_status} → 차단기 열기 시도", flush=True)
                _post(f"http://localhost:{ENTRY_BARRIER_PORT}/open", {})
            print("[VC] 입차 차단기 열림 대기…", flush=True)

        entry_wait_t += dt

        if entry_wait_t >= 2.0:
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
            if exit_wait_t == 0.0:
                print("[VC] 출차 승인 → 차단기 열기", flush=True)
                _post(f"http://localhost:{EXIT_BARRIER_PORT}/open", {})
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
