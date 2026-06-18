from controller import Robot
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json

GATE       = "entry"
HTTP_PORT  = 8100
MOTOR_NAME = "barrier_motor_entry"
OPEN_HOLD_MS = 8000
POS_OPEN   = -1.57
POS_CLOSE  = 0.0
VELOCITY   = 1.0

TAG = f"[차단기:{GATE}]"

robot    = Robot()
timestep = int(robot.getBasicTimeStep())

motor = robot.getDevice(MOTOR_NAME)
if motor:
    motor.setVelocity(VELOCITY)
    motor.setPosition(POS_CLOSE)
else:
    print(f"{TAG} 모터 '{MOTOR_NAME}' 없음")

_lock      = threading.Lock()
_cmd_queue = []
_is_open   = False


def _enqueue(cmd: str) -> None:
    with _lock:
        _cmd_queue.append(cmd)


class BarrierHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/open":
            _enqueue("open")
            self._ok({"status": "ok", "gate": GATE})
            print(f"{TAG} <- POST /open")
        elif self.path == "/close":
            _enqueue("close")
            self._ok({"status": "ok"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            with _lock:
                is_open = _is_open
            self._ok({"gate": GATE, "port": HTTP_PORT, "is_open": is_open})
        else:
            self.send_response(404)
            self.end_headers()

    def _ok(self, body: dict) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *args) -> None:
        pass


server = HTTPServer(("0.0.0.0", HTTP_PORT), BarrierHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()
print(f"{TAG} HTTP 대기 중 -> port {HTTP_PORT}")

open_timer = 0

while robot.step(timestep) != -1:
    with _lock:
        cmds, _cmd_queue[:] = _cmd_queue[:], []

    for cmd in cmds:
        if motor:
            if cmd == "open":
                motor.setPosition(POS_OPEN)
                open_timer = OPEN_HOLD_MS
                with _lock:
                    _is_open = True
                print(f"{TAG} 열림")
            elif cmd == "close":
                motor.setPosition(POS_CLOSE)
                open_timer = 0
                with _lock:
                    _is_open = False
                print(f"{TAG} 닫힘")

    if open_timer > 0:
        open_timer -= timestep
        if open_timer <= 0:
            if motor:
                motor.setPosition(POS_CLOSE)
            with _lock:
                _is_open = False
            print(f"{TAG} 자동 닫힘")
