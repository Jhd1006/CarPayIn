"""
PMS(Parking Management System) HTTP 클라이언트.

유닛 테스트의 FakePmsClient와 동일한 인터페이스를 구현한다.
"""

import json

import httpx

from app.infra.security import sign_webhook_headers


class HttpxPmsClient:
    """httpx 기반 PMS HTTP 클라이언트."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        webhook_secret: str | None = None,
    ):
        """
        Args:
            base_url: PMS 서버 base URL (예: http://pms:8000)
            timeout: 요청 타임아웃(초)
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._webhook_secret = webhook_secret

    # ── UC-PARK-001: 사전 입차 알림 등록 ──────────────────────────────────

    def pre_register_plate(self, *, lot_id: str, plate: str) -> None:
        """
        PMS에 차량 번호판을 사전 등록한다.

        POST /parking/pre-register
        """
        try:
            response = httpx.post(
                f"{self._base_url}/parking/pre-register",
                json={"lot_id": lot_id, "plate": plate},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"pms_pre_register_failed: {e}") from e

    # ── UC-PAY-001: 주차 요금 조회 ────────────────────────────────────────

    def get_parking_fee(
        self, *, lot_id: str, plate: str, pms_session_id: str | None = None
    ) -> dict:
        """
        PMS에서 현재 주차 요금을 조회한다.

        GET /parking/fee?lot_id=&plate=[&pms_session_id=]

        pms_session_id를 함께 전달하면 PMS 쪽에서 lot+plate 조회 실패 시
        session_id로 폴백 조회할 수 있어 더 안정적이다.

        Returns:
            {"amount": int, "duration": int, "currency": str}
        """
        params: dict = {"lot_id": lot_id, "plate": plate}
        if pms_session_id:
            params["pms_session_id"] = pms_session_id
        try:
            response = httpx.get(
                f"{self._base_url}/parking/fee",
                params=params,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"pms_fee_query_failed: {e}") from e

        data = response.json()
        return {
            "amount": data["amount"],
            "duration": data.get("duration_minutes", data.get("duration", 0)),
            "currency": data["currency"],
        }

    # ── UC-PAY-002: 결제 완료 통보 ────────────────────────────────────────

    def notify_payment_complete(
        self,
        *,
        pms_session_id: str,
        carpay_parking_session_id: str,
        carpay_tx_id: str,
        amount: int,
        currency: str,
        approval_no: str,
        idempotency_key: str,
    ) -> dict:
        """
        PMS에 결제 완료를 통보한다.

        POST /payment/complete
        """
        payload = {
            "pms_session_id": pms_session_id,
            "carpay_parking_session_id": carpay_parking_session_id,
            "carpay_tx_id": carpay_tx_id,
            "amount": amount,
            "currency": currency,
            "approval_no": approval_no,
            "idempotency_key": idempotency_key,
        }
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._webhook_secret:
            headers.update(sign_webhook_headers(secret=self._webhook_secret, body=body))

        try:
            response = httpx.post(
                f"{self._base_url}/payment/complete",
                content=body,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise RuntimeError(f"pms_notify_failed: {e}") from e
