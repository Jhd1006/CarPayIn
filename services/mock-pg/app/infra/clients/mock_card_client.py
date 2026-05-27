import httpx


class HttpxMockCardClient:
    def __init__(self, *, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def verify_and_tokenize_card(
        self,
        *,
        user_id: str,
        card_number: str,
        expiry: str,
        cvc: str,
    ) -> dict:
        try:
            response = httpx.post(
                f"{self._base_url}/cards/verify",
                json={
                    "user_id": user_id,
                    "card_number": card_number,
                    "expiry": expiry,
                    "cvc": cvc,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"mock_card_verify_failed: {exc}") from exc
        return response.json()

    def approve_payment(
        self,
        *,
        card_token: str,
        amount: int,
        currency: str,
        idempotency_key: str,
    ) -> dict:
        try:
            response = httpx.post(
                f"{self._base_url}/cards/charge",
                json={
                    "card_token": card_token,
                    "amount": amount,
                    "currency": currency,
                    "idempotency_key": idempotency_key,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"mock_card_charge_failed: {exc}") from exc
        return response.json()
