import hashlib
import hmac

import httpx


class HttpxCarPayInWebhookClient:
    def __init__(
        self,
        *,
        base_url: str,
        webhook_secret: str,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._webhook_secret = webhook_secret.encode("utf-8")
        self._timeout = timeout

    def send_card_registration_webhook(
        self,
        *,
        order_id: str,
        billing_key: str,
        last_four: str,
    ) -> None:
        signature = hmac.new(
            self._webhook_secret,
            order_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        try:
            response = httpx.post(
                f"{self._base_url}/card/webhook",
                json={
                    "order_id": order_id,
                    "billing_key": billing_key,
                    "card_last_four": last_four,
                    "status": "active",
                    "signature": signature,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"carpayin_card_webhook_failed: {exc}") from exc
