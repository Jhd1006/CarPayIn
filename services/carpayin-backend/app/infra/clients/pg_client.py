"""
PG(Payment Gateway) HTTP 클라이언트.

유닛 테스트의 FakePgClient와 동일한 인터페이스를 구현한다.
"""

from urllib.parse import urlencode

import httpx


class HttpxPgClient:
    """httpx 기반 PG HTTP 클라이언트."""

    def __init__(
        self,
        base_url: str,
        public_base_url: str | None = None,
        timeout: float = 10.0,
    ):
        """
        Args:
            base_url: PG 서버 base URL (예: http://mock-pg:8000)
            timeout: 요청 타임아웃(초)
        """
        self._base_url = base_url.rstrip("/")
        self._public_base_url = (public_base_url or base_url).rstrip("/")
        self._timeout = timeout

    # ── UC-CARD-001: 카드 등록 URL 생성 ──────────────────────────────────

    def create_card_registration_url(
        self,
        *,
        order_id: str,
        bank_name: str | None = None,
    ) -> str:
        """
        카드 등록 페이지 URL을 생성한다.

        PG 서버의 카드 등록 페이지 URL을 order_id와 함께 구성한다.
        실제 API 호출 없이 URL을 로컬에서 조립한다.

        Returns:
            카드 등록 페이지 URL (예: http://mock-pg:8000/pg/card-register?order_id=...)
        """
        try:
            query = {"order_id": order_id}
            if bank_name:
                query["card_brand"] = bank_name
            url = f"{self._public_base_url}/pg/card-register?{urlencode(query)}"
            # URL 유효성 검증을 위해 PG 서버에 헬스체크 (선택적)
            return url
        except Exception as e:
            raise RuntimeError(f"pg_url_creation_failed: {e}") from e

    # ── UC-PAY-002: 빌링키 결제 요청 ─────────────────────────────────────

    def charge_billing_key(
        self,
        *,
        billing_key: str,
        amount: int,
        currency: str,
        idempotency_key: str,
    ) -> dict:
        """
        빌링키로 결제를 요청한다.

        POST /pg/payments/billing

        Returns:
            성공: {"success": True, "pg_tx_id": str, "approval_no": str}
            실패: {"success": False, "pg_tx_id": str, "failed_reason": str}
        """
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
