from contextlib import contextmanager
import logging
import threading

from app.infra.db.session import SessionLocal
from app.infra.repositories.payment_notification_outbox_repository import (
    SqlAlchemyPaymentNotificationOutboxRepository,
)


_logger = logging.getLogger("carpayin.payment_outbox_worker")


@contextmanager
def payment_outbox_repository_context():
    session = SessionLocal()
    try:
        yield SqlAlchemyPaymentNotificationOutboxRepository(session)
    finally:
        session.close()


class PaymentOutboxWorker:
    def __init__(
        self,
        *,
        repository_context_factory,
        notification_publisher,
        interval_seconds: int = 5,
        batch_size: int = 100,
        lease_seconds: int = 60,
    ) -> None:
        self._repository_context_factory = repository_context_factory
        self._publisher = notification_publisher
        self._interval = interval_seconds
        self._batch_size = batch_size
        self._lease_seconds = lease_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="payment-outbox-worker",
        )
        self._thread.start()
        _logger.info(
            "payment_outbox_worker started (interval=%ds)",
            self._interval,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval):
            try:
                self.run_once()
            except Exception as exc:
                _logger.warning("payment_outbox_scan_error: %s", exc)

    def run_once(self) -> int:
        with self._repository_context_factory() as repository:
            notifications = repository.claim_due(
                limit=self._batch_size,
                lease_seconds=self._lease_seconds,
            )
            for notification in notifications:
                self._publish_one(repository, notification)
            return len(notifications)

    def _publish_one(self, repository, notification: dict) -> None:
        notification_id = notification["notification_id"]
        try:
            self._publisher.publish_payment_notification(
                **notification["payload"]
            )
        except Exception as exc:
            attempts = notification["attempts"]
            retry_delay_seconds = min(5 * (2 ** max(attempts - 1, 0)), 300)
            repository.mark_failed(
                notification_id,
                reason=str(exc),
                retry_delay_seconds=retry_delay_seconds,
            )
            _logger.warning(
                "payment_outbox_publish_failed: notification_id=%s, error=%s",
                notification_id,
                exc,
            )
            return

        repository.mark_published(notification_id)
        _logger.info(
            "payment_outbox_publish_success: notification_id=%s",
            notification_id,
        )
