#!/usr/bin/env bash
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORLD_FILE="${WEBOTS_WORLD:-$PROJECT_DIR/worlds/Car Pay-in.wbt}"

# ── 모드 결정 ────────────────────────────────────────────────────────────────
#
#  우선순위:
#  1) PARKING_PMS_URL / BACKEND_URL 환경변수가 이미 세팅된 경우 → 그대로 사용
#  2) --local 또는 인자 없이 localhost:8000 이 응답하는 경우     → 로컬 모드
#  3) ./start_carpayin_webots.sh <노트북IP>                       → 원격 모드
#  4) ./start_carpayin_webots.sh --aws                            → AWS 모드
#     (CARPAYIN_BACKEND_URL / CARPAYIN_PMS_URL 환경변수 필요)
#
ARG="${1:-}"

if [[ -n "${PARKING_PMS_URL:-}" && -n "${BACKEND_URL:-}" ]]; then
  echo "[CarPayIn] 환경변수 모드 – PARKING_PMS_URL=${PARKING_PMS_URL}"

elif [[ "$ARG" == "--aws" ]]; then
  # ── AWS 모드 ──────────────────────────────────────────────────────────────
  if [[ -z "${CARPAYIN_PMS_URL:-}" || -z "${CARPAYIN_BACKEND_URL:-}" ]]; then
    echo "AWS 모드에서는 환경변수가 필요합니다:"
    echo "  export CARPAYIN_PMS_URL=https://<pms-alb-or-domain>"
    echo "  export CARPAYIN_BACKEND_URL=https://<carpayin-backend-alb-or-domain>"
    exit 1
  fi
  export BACKEND_URL="$CARPAYIN_BACKEND_URL"
  export PARKING_PMS_URL="$CARPAYIN_PMS_URL"
  export GPS_PROXY_URL=""
  export ADB_HOST=""
  export ADB_TARGET=""
  echo "[CarPayIn] AWS 모드 – PMS: $PARKING_PMS_URL"

elif [[ "$ARG" == "--local" || -z "$ARG" ]]; then
  # ── 로컬 모드 ──────────────────────────────────────────────────────────────
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    export BACKEND_URL="http://localhost:8000"
    export PARKING_PMS_URL="http://localhost:8001"
    export GPS_PROXY_URL=""
    export ADB_HOST=""
    export ADB_TARGET="emulator-5554"
    echo "[CarPayIn] 로컬 모드 – 백엔드/PMS/에뮬레이터가 모두 이 머신에서 실행 중"
  else
    echo "로컬 모드: localhost:8000 에 응답이 없습니다. 백엔드가 실행 중인지 확인하세요."
    exit 1
  fi

else
  # ── 원격 노트북 모드 ───────────────────────────────────────────────────────
  NOTEBOOK_IP="$ARG"
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
for candidate in \
    /usr/local/webots/webots \
    /snap/bin/webots \
    /opt/webots/webots \
    "$HOME/webots/webots"; do
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
