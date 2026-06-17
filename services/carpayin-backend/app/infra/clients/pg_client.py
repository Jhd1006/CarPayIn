"""HTTP client for the PG service."""

import httpx


class HttpxPgClient:
    """httpx-based PG HTTP client."""

    def __init__(
        self,
        base_url: str,
        public_base_url: str | None = None,
        card_webhook_url: str | None = None,
        timeout: float = 10.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._public_base_url = (public_base_url or base_url).rstrip("/")
        self._card_webhook_url = (card_webhook_url or "").rstrip("/")
        self._timeout = timeout

    def create_card_registration_url(
        self,
        *,
        order_id: str,
        car_id: str = "",
        plate: str = "",
        bank_name: str | None = None,
    ) -> str:
        """Create a PG-owned WebView session and return its public URL."""
        try:
            response = httpx.post(
                f"{self._base_url}/pg/internal/card-registration/sessions",
                json={
                    "order_id": order_id,
                    "car_id": car_id,
                    "plate": plate,
                    "card_brand": bank_name or "",
                    "callback_url": self._card_webhook_url,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            url = data.get("webview_url") or data.get("pg_url")
            if not url:
                raise RuntimeError("missing_webview_url")
            # Mock-PG가 internal URL 기준으로 URL을 생성하므로 public URL로 교체
            if self._public_base_url != self._base_url and url.startswith(self._base_url):
                url = self._public_base_url + url[len(self._base_url):]
            return url
        except Exception as e:
            raise RuntimeError(f"pg_url_creation_failed: {e}") from e

    def charge_billing_key(
        self,
        *,
        billing_key: str,
        amount: int,
        currency: str,
        idempotency_key: str,
    ) -> dict:
        """Request a billing payment through the PG internal API."""
        try:
            response = httpx.post(
                f"{self._base_url}/pg/payments/billing",
                json={
                    "billing_key": billing_key,
                    "amount": amount,
                    "currency": currency,
                    "idempotency_key": idempotency_key,
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as e:
            raise RuntimeError(f"pg_charge_failed: {e}") from e

        if response.status_code >= 500:
            raise RuntimeError(f"pg_charge_failed: HTTP {response.status_code}")

        data = response.json()

        if response.status_code == 400 or data.get("status") == "failed":
            return {
                "success": False,
                "pg_tx_id": data.get("pg_tx_id", ""),
                "failed_reason": data.get("failed_reason", "payment_failed"),
            }

        return {
            "success": True,
            "pg_tx_id": data["pg_tx_id"],
            "approval_no": data["approval_no"],
        }
