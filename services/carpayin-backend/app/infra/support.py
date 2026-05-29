import logging
import uuid


class UuidOrderIdGenerator:
    def generate(self) -> str:
        return f"order-{uuid.uuid4().hex}"


class PlateNormalizer:
    def normalize(self, plate: str) -> str:
        return plate.replace(" ", "").replace("-", "").strip()


class LoggingNotificationPublisher:
    def __init__(self) -> None:
        self._logger = logging.getLogger("carpayin.notifications")

    def publish_entry_notification(self, **payload) -> None:
        self._logger.info("parking_entry", extra={"notification": payload})

    def publish_payment_notification(self, **payload) -> None:
        self._logger.info("payment_complete", extra={"notification": payload})
