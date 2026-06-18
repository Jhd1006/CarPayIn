import json
import logging
import os
import uuid

try:
    import paho.mqtt.publish as mqtt_publish
except ImportError:  # pragma: no cover - local tests may not install MQTT extras
    mqtt_publish = None

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None


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


class MqttNotificationPublisher(LoggingNotificationPublisher):
    def __init__(
        self,
        *,
        host: str,
        port: int,
        enabled: bool = True,
    ) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._enabled = enabled and mqtt_publish is not None

    def publish_entry_notification(self, **payload) -> None:
        super().publish_entry_notification(**payload)
        car_id = payload.get("car_id")
        if not car_id:
            return
        self._publish(
            topic=f"parking/confirmed/{car_id}",
            payload={
                "session_id": payload.get("session_id", ""),
                "lot_id": payload.get("lot_id", ""),
                "entry_time": payload.get("entry_time", ""),
            },
        )

    def publish_payment_notification(self, **payload) -> None:
        super().publish_payment_notification(**payload)
        car_id = payload.get("car_id")
        if not car_id:
            return
        self._publish(
            topic=f"payment/complete/{car_id}",
            payload={
                "transaction_id": payload.get("tx_id", ""),
                "approval_number": payload.get("approval_no", ""),
                "lot_id": payload.get("lot_id", ""),
                "amount": payload.get("amount", 0),
            },
        )

    def _publish(self, *, topic: str, payload: dict) -> None:
        if not self._enabled:
            self._logger.info("mqtt_skipped", extra={"topic": topic, "payload": payload})
            return
        try:
            mqtt_publish.single(
                topic,
                json.dumps(payload, ensure_ascii=False),
                hostname=self._host,
                port=self._port,
                qos=1,
            )
        except Exception as exc:  # pragma: no cover - depends on local broker
            self._logger.warning(
                "mqtt_publish_failed",
                extra={"topic": topic, "error": str(exc)},
            )


class SqsNotificationPublisher(LoggingNotificationPublisher):
    def __init__(self, *, queue_url: str, region: str = "ap-northeast-2") -> None:
        super().__init__()
        self._queue_url = queue_url
        self._sqs = boto3.client("sqs", region_name=region) if boto3 else None

    def publish_entry_notification(self, **payload) -> None:
        super().publish_entry_notification(**payload)
        car_id = payload.get("car_id")
        if not car_id:
            return
        self._send({
            "event_type": "parking.confirmed",
            "car_id": car_id,
            "payload": {
                "session_id": payload.get("session_id", ""),
                "lot_id": payload.get("lot_id", ""),
                "entry_time": payload.get("entry_time", ""),
            },
        })

    def publish_payment_notification(self, **payload) -> None:
        super().publish_payment_notification(**payload)
        car_id = payload.get("car_id")
        if not car_id:
            return
        self._send({
            "event_type": "payment.completed",
            "car_id": car_id,
            "payload": {
                "transaction_id": payload.get("tx_id", ""),
                "approval_number": payload.get("approval_no", ""),
                "lot_id": payload.get("lot_id", ""),
                "amount": int(payload.get("amount", 0)),
            },
        })

    def _send(self, body: dict) -> None:
        if not self._sqs:
            self._logger.warning("sqs_unavailable", extra={"body": body})
            return
        try:
            self._sqs.send_message(
                QueueUrl=self._queue_url,
                MessageBody=json.dumps(body, ensure_ascii=False),
            )
        except Exception as exc:
            self._logger.warning("sqs_publish_failed", extra={"error": str(exc)})


def build_notification_publisher() -> LoggingNotificationPublisher:
    queue_url = os.getenv("SQS_NOTIFICATION_QUEUE_URL", "").strip()
    publish_enabled = os.getenv("SQS_NOTIFICATION_PUBLISH_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }
    if queue_url and publish_enabled:
        return SqsNotificationPublisher(queue_url=queue_url)

    # fallback: MQTT (로컬 개발용)
    enabled = os.getenv("MQTT_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }
    host = os.getenv("MQTT_HOST", "localhost").strip() or "localhost"
    port = int(os.getenv("MQTT_PORT", "1883"))
    return MqttNotificationPublisher(host=host, port=port, enabled=enabled)
