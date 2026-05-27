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
        self._webhook_token = webhook_token
        self._timeout = timeout

    def send_entry_webhook(
        self,
        *,
        pms_session_id: str,
        lot_id: str,
        plate: str,
        entry_time: str,
    ) -> None:
        try:
            response = httpx.post(
                f"{self._base_url}/webhook/entry",
                headers={"X-PMS-Signature": self._webhook_token},
                json={
                    "pms_session_id": pms_session_id,
                    "lot_id": lot_id,
                    "plate": plate,
                    "entry_time": entry_time,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"carpayin_entry_webhook_failed: {exc}") from exc
