#!/usr/bin/env bash
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORLD_FILE="${WEBOTS_WORLD:-$PROJECT_DIR/worlds/Car Pay-in.wbt}"

# ── 로컬 모드 자동 감지 ─────────────────────────────────────────────────────
# 인자 없이 실행하거나 --local이면 localhost 기준으로 동작
USE_LOCAL=false
if [[ "${1:-}" == "--local" || -z "${1:-}" ]]; then
  # 백엔드가 localhost:8000에 응답하면 로컬 모드
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    USE_LOCAL=true
  fi
fi

if $USE_LOCAL; then
  export BACKEND_URL="http://localhost:8000"
  export PARKING_PMS_URL="http://localhost:8001"
  export GPS_PROXY_URL=""
  export ADB_HOST=""
  export ADB_TARGET="emulator-5554"
  echo "[CarPayIn] 로컬 모드 – 백엔드/PMS/에뮬레이터가 모두 이 머신에서 실행 중"
else
  # ── 원격 노트북 모드 (에뮬레이터가 다른 PC에 있을 때) ───────────────────
  NOTEBOOK_IP="${CARPAYIN_NOTEBOOK_IP:-${1:-}}"
  if [[ -z "$NOTEBOOK_IP" ]]; then
    echo "노트북 IP를 첫 번째 인자로 전달하거나 CARPAYIN_NOTEBOOK_IP 환경변수를 설정하세요."
    echo "  예) $0 192.168.1.100"
    echo "  또는: $0 --local  (모든 서비스가 이 머신에서 실행 중일 때)"
    exit 1
  fi
  export BACKEND_URL="http://$NOTEBOOK_IP:8000"
  export PARKING_PMS_URL="http://$NOTEBOOK_IP:8001"
  export GPS_PROXY_URL="http://$NOTEBOOK_IP:5600"
  export ADB_HOST="$NOTEBOOK_IP"
  export ADB_TARGET=""
  echo "[CarPayIn] 원격 노트북 모드 – 노트북: $NOTEBOOK_IP"
fi

export WEBOTS_VIN="${WEBOTS_VIN:-TESTVIN001}"
export WEBOTS_PLATE="${WEBOTS_PLATE:-12가3456}"
export WEBOTS_LOT_ID="${WEBOTS_LOT_ID:-LOT_TEST_01}"
export WEBOTS_DRIVE_MODE="${WEBOTS_DRIVE_MODE:-auto}"

echo "[CarPayIn] Backend:    $BACKEND_URL"
echo "[CarPayIn] PMS:        $PARKING_PMS_URL"
echo "[CarPayIn] GPS proxy:  ${GPS_PROXY_URL:-adb-direct}"
echo "[CarPayIn] World:      $WORLD_FILE"
echo "[CarPayIn] Drive mode: $WEBOTS_DRIVE_MODE"

# ── Webots 실행 파일 탐색 ────────────────────────────────────────────────────
WEBOTS_BIN="${WEBOTS_BIN:-}"
for candidate in     /usr/local/webots/webots     /snap/bin/webots     /opt/webots/webots     "$HOME/webots/webots"; do
  if [[ -z "$WEBOTS_BIN" && -x "$candidate" ]]; then
    WEBOTS_BIN="$candidate"
  fi
done
if [[ -z "$WEBOTS_BIN" ]]; then
  WEBOTS_BIN="$(command -v webots 2>/dev/null || true)"
fi
if [[ -z "$WEBOTS_BIN" ]]; then
  echo "Webots 실행 파일을 찾을 수 없습니다. WEBOTS_BIN=/path/to/webots 를 설정하세요."
  exit 1
fi

echo "[CarPayIn] Webots:     $WEBOTS_BIN"
exec "$WEBOTS_BIN" "$WORLD_FILE"
