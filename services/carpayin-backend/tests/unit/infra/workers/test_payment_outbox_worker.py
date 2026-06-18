from contextlib import contextmanager

from app.infra.workers.payment_outbox_worker import PaymentOutboxWorker


PAYLOAD = {
    "session_id": "session-001",
    "car_id": "car-001",
    "lot_id": "lot-001",
    "tx_id": "tx-001",
    "amount": 5000,
    "currency": "KRW",
    "approval_no": "APPROVAL-001",
}


class FakeRepository:
    def __init__(self, notifications):
        self.notifications = notifications
        self.claim_calls = []
        self.published = []
        self.failed = []

    def claim_due(self, *, limit, lease_seconds):
        self.claim_calls.append(
            {"limit": limit, "lease_seconds": lease_seconds}
        )
        return list(self.notifications)

    def mark_published(self, notification_id):
        self.published.append(notification_id)

    def mark_failed(
        self,
        notification_id,
        *,
        reason,
        retry_delay_seconds,
    ):
        self.failed.append(
            {
                "notification_id": notification_id,
                "reason": reason,
                "retry_delay_seconds": retry_delay_seconds,
            }
        )


class FakePublisher:
    def __init__(self, *, error=None):
        self.error = error
        self.payloads = []

    def publish_payment_notification(self, **payload):
        self.payloads.append(payload)
        if self.error:
            raise self.error


def repository_context(repository):
    @contextmanager
    def factory():
        yield repository

    return factory


def test_run_once_publishes_and_marks_outbox_event():
    repository = FakeRepository(
        [
            {
                "notification_id": "notification-001",
                "payload": PAYLOAD,
                "attempts": 1,
                "max_attempts": 5,
            }
        ]
    )
    publisher = FakePublisher()
    worker = PaymentOutboxWorker(
        repository_context_factory=repository_context(repository),
        notification_publisher=publisher,
        batch_size=25,
        lease_seconds=45,
    )

    processed = worker.run_once()

    assert processed == 1
    assert publisher.payloads == [PAYLOAD]
    assert repository.published == ["notification-001"]
    assert repository.failed == []
    assert repository.claim_calls == [{"limit": 25, "lease_seconds": 45}]


def test_run_once_marks_failure_with_exponential_backoff():
    repository = FakeRepository(
        [
            {
                "notification_id": "notification-002",
                "payload": PAYLOAD,
                "attempts": 3,
                "max_attempts": 5,
            }
        ]
    )
    publisher = FakePublisher(error=RuntimeError("sqs unavailable"))
    worker = PaymentOutboxWorker(
        repository_context_factory=repository_context(repository),
        notification_publisher=publisher,
    )

    processed = worker.run_once()

    assert processed == 1
    assert repository.published == []
    assert repository.failed == [
        {
            "notification_id": "notification-002",
            "reason": "sqs unavailable",
            "retry_delay_seconds": 20,
        }
    ]
