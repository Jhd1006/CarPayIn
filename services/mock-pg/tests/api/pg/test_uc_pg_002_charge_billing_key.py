"""
billing key 결제 승인 API 테스트.
UC-PG-002: POST /payments/billing
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_charge_billing_key_service
from app.application.pg.charge_billing_key import ChargeBillingKeyResult
from app.main import app


VALID_BILLING_KEY = "bk-001"
VALID_AMOUNT = 5000
VALID_CURRENCY = "KRW"
VALID_IDEMPOTENCY_KEY = "idem-001"
VALID_TX_ID = "tx-001"
VALID_APPROVAL_NO = "APPR-001"


class StubChargeBillingKeyService:
    def __init__(self, status="success", approval_no=VALID_APPROVAL_NO):
        self.status = status
        self.approval_no = approval_no

    def execute(self, command):
        return ChargeBillingKeyResult(
            status=self.status,
            tx_id=VALID_TX_ID,
            approval_no=self.approval_no,
        )


@pytest.fixture
def api_client_with_success_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_charge_billing_key_service] = (
        lambda: StubChargeBillingKeyService()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_failed_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_charge_billing_key_service] = (
        lambda: StubChargeBillingKeyService(status="failed", approval_no=None)
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


def valid_payment_payload():
    return {
        "billing_key": VALID_BILLING_KEY,
        "amount": VALID_AMOUNT,
        "currency": VALID_CURRENCY,
        "idempotency_key": VALID_IDEMPOTENCY_KEY,
    }


class TestChargeBillingKeyApi:
    """UC-PG-002 - POST /payments/billing"""

    def test_active_billing_key_returns_success(
        self,
        api_client_with_success_service_stub,
    ):
        response = api_client_with_success_service_stub.post(
            "/payments/billing",
            json=valid_payment_payload(),
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "success",
            "tx_id": VALID_TX_ID,
            "approval_no": VALID_APPROVAL_NO,
        }

    def test_duplicate_idempotency_key_returns_existing_result(
        self,
        api_client_with_success_service_stub,
    ):
        first_response = api_client_with_success_service_stub.post(
            "/payments/billing",
            json=valid_payment_payload(),
        )
        second_response = api_client_with_success_service_stub.post(
            "/payments/billing",
            json=valid_payment_payload(),
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["tx_id"] == VALID_TX_ID

    def test_inactive_billing_key_returns_failed(
        self,
        api_client_with_failed_service_stub,
    ):
        response = api_client_with_failed_service_stub.post(
            "/payments/billing",
            json=valid_payment_payload(),
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "failed",
            "tx_id": VALID_TX_ID,
            "approval_no": None,
        }

    def test_missing_billing_key_returns_422(
        self,
        api_client_with_success_service_stub,
    ):
        payload = valid_payment_payload()
        payload.pop("billing_key")

        response = api_client_with_success_service_stub.post(
            "/payments/billing",
            json=payload,
        )

        assert response.status_code == 422
