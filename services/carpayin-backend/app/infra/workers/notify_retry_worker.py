"""
MQTT 알림 재시도 워커.

MQTT 발행 실패 시 Redis에 저장된 이벤트를 주기적으로 재시도한다:
  - entry_notify_retry:{session_id}  : 입차 확정 알림
  - pms_payment_retry:{tx_id}        : PMS 결제 완료 통보
"""

import logging
import threading

_logger = logging.getLogger("carpayin.notify_retry_worker")


class NotifyRetryWorker:
    def __init__(
        self,
        *,
        redis_client,
        notification_publisher,
        pms_client,
        interval_seconds: int = 60,
    ) -> None:
        self._redis = redis_client
        self._publisher = notification_publisher
        self._pms_client = pms_client
        self._interval = interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="notify-retry-worker"
        )
        self._thread.start()
        _logger.info("notify_retry_worker started (interval=%ds)", self._interval)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval):
            try:
                self._process_entry_retries()
            except Exception as exc:
                _logger.warning("entry_retry_scan_error: %s", exc)
            try:
                self._process_payment_retries()
            except Exception as exc:
                _logger.warning("payment_retry_scan_error: %s", exc)

    # ── 입차 알림 재시도 ──────────────────────────────────────────────────────

    def _process_entry_retries(self) -> None:
        cursor = 0
        while True:
            cursor, keys = self._redis.scan(
                cursor, match="entry_notify_retry:*", count=100
            )
            for key in keys:
                self._retry_entry(key)
            if cursor == 0:
                break

    def _retry_entry(self, key: str) -> None:
        import json

        raw = self._redis.get(key)
        if not raw:
            return
        try:
            event = json.loads(raw)
        except Exception:
            self._redis.delete(key)
            return

        session_id = event.get("session_id", "")
        try:
            self._publisher.publish_entry_notification(
                session_id=session_id,
                car_id=event.get("car_id", ""),
                lot_id=event.get("lot_id", ""),
                entry_time=event.get("entry_time", ""),
            )
            self._redis.delete(key)
            _logger.info("entry_notify_retry_success: session_id=%s", session_id)
        except Exception as exc:
            _logger.warning(
                "entry_notify_retry_failed: session_id=%s, error=%s", session_id, exc
            )

    # ── PMS 결제 완료 알림 재시도 ─────────────────────────────────────────────

    def _process_payment_retries(self) -> None:
        cursor = 0
        while True:
            cursor, keys = self._redis.scan(
                cursor, match="pms_payment_retry:*", count=100
            )
            for key in keys:
                self._retry_payment(key)
            if cursor == 0:
                break

    def _retry_payment(self, key: str) -> None:
        import json

        raw = self._redis.get(key)
        if not raw:
            return
        try:
            event = json.loads(raw)
        except Exception:
            self._redis.delete(key)
            return

        tx_id = event.get("tx_id", "")
        payload = event.get("payload", {})
        try:
            self._pms_client.notify_payment_complete(**payload)
            self._redis.delete(key)
            _logger.info("pms_payment_retry_success: tx_id=%s", tx_id)
        except Exception as exc:
            _logger.warning(
                "pms_payment_retry_failed: tx_id=%s, error=%s", tx_id, exc
            )
