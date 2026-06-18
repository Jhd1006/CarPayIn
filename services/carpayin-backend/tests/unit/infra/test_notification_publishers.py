import pytest

from app.infra import support
from app.infra.support import (
    LoggingNotificationPublisher,
    MqttNotificationPublisher,
    SqsNotificationPublisher,
)


class FailingMqttModule:
    @staticmethod
    def single(*args, **kwargs):
        raise RuntimeError("mqtt unavailable")


class FailingSqsClient:
    def send_message(self, **kwargs):
        raise RuntimeError("sqs unavailable")


def test_mqtt_publisher_propagates_delivery_failure(monkeypatch):
    monkeypatch.setattr(support, "mqtt_publish", FailingMqttModule)
    publisher = MqttNotificationPublisher(
        host="mqtt.test",
        port=1883,
        enabled=True,
    )

    with pytest.raises(RuntimeError, match="mqtt unavailable"):
        publisher.publish_payment_notification(
            car_id="car-001",
            tx_id="tx-001",
            approval_no="approval-001",
            lot_id="lot-001",
            amount=5000,
        )


def test_sqs_publisher_propagates_delivery_failure():
    publisher = object.__new__(SqsNotificationPublisher)
    LoggingNotificationPublisher.__init__(publisher)
    publisher._queue_url = "https://sqs.test/queue"
    publisher._sqs = FailingSqsClient()

    with pytest.raises(RuntimeError, match="sqs unavailable"):
        publisher.publish_payment_notification(
            car_id="car-001",
            tx_id="tx-001",
            approval_no="approval-001",
            lot_id="lot-001",
            amount=5000,
        )
