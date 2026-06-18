from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models import PaymentNotificationOutbox


class SqlAlchemyPaymentNotificationOutboxRepository:
    def __init__(self, session: Session):
        self.session = session

    def claim_due(
        self,
        *,
        limit: int = 100,
        lease_seconds: int = 60,
    ) -> list[dict]:
        now = datetime.now(timezone.utc)
        statement = (
            select(PaymentNotificationOutbox)
            .where(
                PaymentNotificationOutbox.status.in_(
                    ("pending", "failed", "publishing")
                ),
                PaymentNotificationOutbox.next_attempt_at <= now,
                PaymentNotificationOutbox.attempts
                < PaymentNotificationOutbox.max_attempts,
            )
            .order_by(PaymentNotificationOutbox.created_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        notifications = list(self.session.scalars(statement))

        lease_expires_at = now + timedelta(seconds=lease_seconds)
        for notification in notifications:
            notification.status = "publishing"
            notification.attempts += 1
            notification.next_attempt_at = lease_expires_at
            notification.updated_at = now

        self.session.commit()
        return [self._to_dict(notification) for notification in notifications]

    def mark_published(self, notification_id: str) -> None:
        notification = self._get(notification_id)
        now = datetime.now(timezone.utc)
        notification.status = "published"
        notification.published_at = now
        notification.failed_reason = None
        notification.updated_at = now
        self.session.commit()

    def mark_failed(
        self,
        notification_id: str,
        *,
        reason: str,
        retry_delay_seconds: int,
    ) -> None:
        notification = self._get(notification_id)
        now = datetime.now(timezone.utc)
        notification.failed_reason = reason
        notification.updated_at = now

        if notification.attempts >= notification.max_attempts:
            notification.status = "dead"
        else:
            notification.status = "failed"
            notification.next_attempt_at = now + timedelta(
                seconds=retry_delay_seconds
            )

        self.session.commit()

    def _get(self, notification_id: str) -> PaymentNotificationOutbox:
        notification = self.session.get(
            PaymentNotificationOutbox,
            UUID(notification_id),
        )
        if notification is None:
            raise LookupError("payment_notification_not_found")
        return notification

    @staticmethod
    def _to_dict(notification: PaymentNotificationOutbox) -> dict:
        return {
            "notification_id": str(notification.notification_id),
            "tx_id": str(notification.tx_id),
            "session_id": str(notification.session_id),
            "car_id": notification.car_id,
            "event_type": notification.event_type,
            "destination": notification.destination,
            "payload": dict(notification.payload),
            "attempts": notification.attempts,
            "max_attempts": notification.max_attempts,
        }
