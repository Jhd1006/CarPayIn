"""
card token 결제 승인 API 테스트.
UC-CARDCO-002: POST /cards/charge
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_approve_card_payment_service
from app.application.card.approve_card_payment import ApproveCardPaymentResult
from app.main import app


VALID_CARD_TOKEN = "card-token-001"
VALID_AMOUNT = 5000
VALID_CURRENCY = "KRW"
VALID_IDEMPOTENCY_KEY = "idem-001"
VALID_TX_ID = "card-tx-001"
VALID_APPROVAL_NO = "CARD-001"


class StubApproveCardPaymentService:
    def __init__(self, status="success", approval_no=VALID_APPROVAL_NO):
        self.status = status
        self.approval_no = approval_no

    def execute(self, command):
        return ApproveCardPaymentResult(
            status=self.status,
            tx_id=VALID_TX_ID,
            approval_no=self.approval_no,
        )


class StubApproveCardPaymentServiceThatFails:
    def execute(self, command):
        raise ValueError("invalid_amount")


@pytest.fixture
def api_client_with_success_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_approve_card_payment_service] = (
        lambda: StubApproveCardPaymentService()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_failed_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_approve_card_payment_service] = (
        lambda: StubApproveCardPaymentService(status="failed", approval_no=None)
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_error_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_approve_card_payment_service] = (
        lambda: StubApproveCardPaymentServiceThatFails()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


def valid_charge_payload():
    return {
        "card_token": VALID_CARD_TOKEN,
        "amount": VALID_AMOUNT,
        "currency": VALID_CURRENCY,
        "idempotency_key": VALID_IDEMPOTENCY_KEY,
    }


class TestApproveCardPaymentApi:
    """UC-CARDCO-002 - POST /cards/charge"""

    def test_active_card_token_returns_success_tx(
        self,
        api_client_with_success_service_stub,
    ):
        response = api_client_with_success_service_stub.post(
            "/cards/charge",
            json=valid_charge_payload(),
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "success",
            "tx_id": VALID_TX_ID,
            "approval_no": VALID_APPROVAL_NO,
        }

    def test_duplicate_idempotency_key_returns_existing_tx(
        self,
        api_client_with_success_service_stub,
    ):
        first_response = api_client_with_success_service_stub.post(
            "/cards/charge",
            json=valid_charge_payload(),
        )
        second_response = api_client_with_success_service_stub.post(
            "/cards/charge",
            json=valid_charge_payload(),
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["tx_id"] == VALID_TX_ID

    def test_inactive_card_token_returns_failed(
        self,
        api_client_with_failed_service_stub,
    ):
        response = api_client_with_failed_service_stub.post(
            "/cards/charge",
            json=valid_charge_payload(),
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "failed",
            "tx_id": VALID_TX_ID,
            "approval_no": None,
        }

    def test_invalid_amount_returns_400(self, api_client_with_error_service_stub):
        payload = valid_charge_payload()
        payload["amount"] = 0

        response = api_client_with_error_service_stub.post(
            "/cards/charge",
            json=payload,
        )

        assert response.status_code == 400
        assert response.json()["message"] == "invalid_amount"

    def test_missing_card_token_returns_422(
        self,
        api_client_with_success_service_stub,
    ):
        payload = valid_charge_payload()
        payload.pop("card_token")

        response = api_client_with_success_service_stub.post(
            "/cards/charge",
            json=payload,
        )

        assert response.status_code == 422
