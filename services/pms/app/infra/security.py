import hashlib
import hmac
import time


class WebhookSignatureVerifier:
    def __init__(self, secret: str, tolerance_seconds: int = 5 * 60):
        self._secret = secret.encode("utf-8")
        self._tolerance_seconds = tolerance_seconds

    def verify(self, *, timestamp: str, signature: str, body: bytes) -> bool:
        try:
            timestamp_int = int(timestamp)
        except (TypeError, ValueError):
            return False

        now = int(time.time())
        if abs(now - timestamp_int) > self._tolerance_seconds:
            return False

        body_hash = hashlib.sha256(body).hexdigest()
        expected = hmac.new(
            self._secret,
            f"{timestamp}.{body_hash}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
