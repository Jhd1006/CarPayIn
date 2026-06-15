import hashlib
import hmac
import json
import time

import httpx


class HttpxCarPayInWebhookClient:
    def __init__(
        self,
        *,
        base_url: str,
        webhook_token: str,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._webhook_secret = webhook_token.encode("utf-8")
        self._timeout = timeout

    def send_entry_webhook(
        self,
        *,
        pms_session_id: str,
        lot_id: str,
        plate: str,
        entry_time: str,
    ) -> None:
        payload = {
            "pms_session_id": pms_session_id,
            "lot_id": lot_id,
            "plate": plate,
            "entry_time": entry_time,
        }
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        timestamp = str(int(time.time()))
        body_hash = hashlib.sha256(body).hexdigest()
        signature = hmac.new(
            self._webhook_secret,
            f"{timestamp}.{body_hash}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        try:
            response = httpx.post(
                f"{self._base_url}/webhook/entry",
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Timestamp": timestamp,
                    "X-Webhook-Signature": signature,
                },
                content=body,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"carpayin_entry_webhook_failed: {exc}") from exc
