"""
결제 완료 기록 API 테스트.
UC-PMS-004: POST /payment/complete
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_record_payment_complete_service
from app.application.pms.record_payment_complete import RecordPaymentCompleteResult
from app.main import app


VALID_PMS_SESSION_ID = "pms-sess-001"
VALID_CARPAY_SESSION_ID = "parking-session-001"
VALID_TX_ID = "tx-001"
VALID_AMOUNT = 5000
VALID_CURRENCY = "KRW"
VALID_APPROVAL_NO = "APPR-001"
VALID_IDEMPOTENCY_KEY = "idem-001"


class StubRecordPaymentCompleteService:
    def execute(self, command):
        return RecordPaymentCompleteResult(status="success")


@pytest.fixture
def api_client_with_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_record_payment_complete_service] = (
        lambda: StubRecordPaymentCompleteService()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


def valid_payment_payload():
    return {
        "pms_session_id": VALID_PMS_SESSION_ID,
        "carpay_parking_session_id": VALID_CARPAY_SESSION_ID,
        "carpay_tx_id": VALID_TX_ID,
        "amount": VALID_AMOUNT,
        "currency": VALID_CURRENCY,
        "approval_no": VALID_APPROVAL_NO,
        "idempotency_key": VALID_IDEMPOTENCY_KEY,
    }


class TestRecordPaymentCompleteApi:
    """UC-PMS-004 - POST /payment/complete"""

    def test_payment_complete_returns_success(self, api_client_with_service_stub):
        response = api_client_with_service_stub.post(
            "/payment/complete",
            json=valid_payment_payload(),
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "success",
            "pms_session_id": VALID_PMS_SESSION_ID,
            "carpay_tx_id": VALID_TX_ID,
        }

    def test_openapi_prefixed_path_returns_success(self, api_client_with_service_stub):
        response = api_client_with_service_stub.post(
            "/pms/payment/complete",
            json=valid_payment_payload(),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_duplicate_idempotency_key_returns_existing_success(
        self,
        api_client_with_service_stub,
    ):
        first_response = api_client_with_service_stub.post(
            "/payment/complete",
            json=valid_payment_payload(),
        )
        second_response = api_client_with_service_stub.post(
            "/payment/complete",
            json=valid_payment_payload(),
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["status"] == "success"

    def test_missing_idempotency_key_returns_422(self, api_client_with_service_stub):
        payload = valid_payment_payload()
        payload.pop("idempotency_key")

        response = api_client_with_service_stub.post(
            "/payment/complete",
            json=payload,
        )

        assert response.status_code == 422
