import logging
import os
import urllib.request


class BarrierPublisher:
    """로깅만 수행하는 기본 퍼블리셔 (테스트·로컬 대체용)"""

    def __init__(self) -> None:
        self._logger = logging.getLogger("pms.barrier")

    def open_entry(self, *, pms_session_id: str = "") -> None:
        self._logger.info("barrier_open_entry", extra={"pms_session_id": pms_session_id})

    def open_exit(self, *, pms_session_id: str = "") -> None:
        self._logger.info("barrier_open_exit", extra={"pms_session_id": pms_session_id})


class HttpBarrierPublisher(BarrierPublisher):
    """Webots 차단기 컨트롤러에 HTTP POST로 직접 개방 명령을 전송한다."""

    def __init__(self, *, entry_url: str, exit_url: str, enabled: bool = True) -> None:
        super().__init__()
        self._entry_url = entry_url
        self._exit_url = exit_url
        self._enabled = enabled

    def open_entry(self, *, pms_session_id: str = "") -> None:
        super().open_entry(pms_session_id=pms_session_id)
        self._post(self._entry_url)

    def open_exit(self, *, pms_session_id: str = "") -> None:
        super().open_exit(pms_session_id=pms_session_id)
        self._post(self._exit_url)

    def _post(self, url: str) -> None:
        if not self._enabled:
            self._logger.info("barrier_http_skipped", extra={"url": url})
            return
        try:
            req = urllib.request.Request(
                url,
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                self._logger.info("barrier_http_ok", extra={"url": url, "status": r.status})
        except Exception as exc:
            self._logger.warning("barrier_http_failed", extra={"url": url, "error": str(exc)})


def build_barrier_publisher() -> BarrierPublisher:
    enabled = os.getenv("BARRIER_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
    entry_url = os.getenv("BARRIER_ENTRY_URL", "http://localhost:8100/open")
    exit_url = os.getenv("BARRIER_EXIT_URL", "http://localhost:8101/open")
    return HttpBarrierPublisher(entry_url=entry_url, exit_url=exit_url, enabled=enabled)
