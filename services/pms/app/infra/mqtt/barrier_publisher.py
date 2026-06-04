import json
import logging
import os

try:
    import paho.mqtt.publish as mqtt_publish
except ImportError:  # pragma: no cover - 로컬 테스트 환경에 paho-mqtt 미설치 시 대비
    mqtt_publish = None

TOPIC_BARRIER = "carpayin/barrier"


class BarrierPublisher:
    """로깅만 수행하는 기본 퍼블리셔 (테스트·로컬 대체용)"""

    def __init__(self) -> None:
        self._logger = logging.getLogger("pms.barrier")

    def open_exit(self, *, pms_session_id: str = "") -> None:
        self._logger.info("barrier_open_exit", extra={"pms_session_id": pms_session_id})


class MqttBarrierPublisher(BarrierPublisher):
    """EC2 Mosquitto 브로커로 출구 차단기 개방 명령을 발행한다."""

    def __init__(self, *, host: str, port: int, enabled: bool = True) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._enabled = enabled and mqtt_publish is not None

    def open_exit(self, *, pms_session_id: str = "") -> None:
        super().open_exit(pms_session_id=pms_session_id)
        self._publish({"gate": "exit", "action": "open"})

    def _publish(self, payload: dict) -> None:
        if not self._enabled:
            self._logger.info(
                "mqtt_skipped",
                extra={"topic": TOPIC_BARRIER, "payload": payload},
            )
            return
        try:
            mqtt_publish.single(
                TOPIC_BARRIER,
                json.dumps(payload),
                hostname=self._host,
                port=self._port,
                qos=1,
            )
        except Exception as exc:
            self._logger.warning(
                "mqtt_publish_failed",
                extra={"topic": TOPIC_BARRIER, "error": str(exc)},
            )


def build_barrier_publisher() -> BarrierPublisher:
    enabled = os.getenv("MQTT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
    host = os.getenv("MQTT_HOST", "localhost").strip() or "localhost"
    port = int(os.getenv("MQTT_PORT", "1883"))
    return MqttBarrierPublisher(host=host, port=port, enabled=enabled)
