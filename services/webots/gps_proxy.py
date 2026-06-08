"""
gps_proxy.py - 노트북에서 실행하는 GPS 프록시 서버
Webots(데스크탑)로부터 GPS 좌표를 받아 adb emu geo fix 를 로컬에서 실행한다.

실행 방법 (노트북 PowerShell):
    python services/webots/gps_proxy.py
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import json


class GpsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/health"):
            self.send_response(404)
            self.end_headers()
            return

        body = json.dumps({"status": "ok", "service": "carpayin-gps-proxy"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            lat = body["lat"]
            lng = body["lng"]
            subprocess.Popen(f"adb emu geo fix {lng} {lat}", shell=True)
            print(f"[GPS] lat={lat:.6f} lng={lng:.6f}")
            self.send_response(200)
            payload = json.dumps({"status": "ok"}).encode()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        except Exception as e:
            print(f"[오류] {e}")
            self.send_response(500)
        self.end_headers()

    def log_message(self, *args):
        pass  # HTTP 기본 로그 출력 억제


if __name__ == "__main__":
    host, port = "0.0.0.0", 5600
    print(f"GPS 프록시 서버 시작: http://{host}:{port}")
    print("Webots에서 GPS 좌표를 받으면 adb emu geo fix 를 실행합니다.")
    print("종료: Ctrl+C")
    try:
        HTTPServer((host, port), GpsHandler).serve_forever()
    except KeyboardInterrupt:
        print("\n서버 종료")
