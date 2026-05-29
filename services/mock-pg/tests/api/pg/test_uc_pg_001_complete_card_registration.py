"""
카드 등록 WebView 완료 API 테스트.
UC-PG-001: POST /card-register
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_complete_card_registration_service
from app.application.pg.complete_card_registration import (
    CompleteCardRegistrationResult,
)
from app.main import app


VALID_ORDER_ID = "order-001"
VALID_CARD_NUMBER = "1234567890123456"
VALID_EXPIRY = "12/28"
VALID_CVC = "123"
VALID_BILLING_KEY = "bk-001"


class StubCompleteCardRegistrationService:
    def __init__(self, status="success", billing_key=VALID_BILLING_KEY):
        self.status = status
        self.billing_key = billing_key

    def execute(self, command):
        return CompleteCardRegistrationResult(
            status=self.status,
            billing_key=self.billing_key,
        )


@pytest.fixture
def api_client_with_success_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_complete_card_registration_service] = (
        lambda: StubCompleteCardRegistrationService()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_failed_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_complete_card_registration_service] = (
        lambda: StubCompleteCardRegistrationService(
            status="failed",
            billing_key=None,
        )
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


def valid_registration_payload():
    return {
        "order_id": VALID_ORDER_ID,
        "card_number": VALID_CARD_NUMBER,
        "expiry": VALID_EXPIRY,
        "cvc": VALID_CVC,
    }


class TestCompleteCardRegistrationApi:
    """UC-PG-001 - POST /card-register"""

    def test_pg_url_opens_card_registration_webview(self):
        with TestClient(app) as client:
            response = client.get(
                "/pg/card-register",
                params={"order_id": VALID_ORDER_ID},
            )

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert f'data-order-id="{VALID_ORDER_ID}"' in response.text
        assert 'id="cardForm"' in response.text
        assert 'id="brandList"' not in response.text
        assert "onRegistrationCompleteV3" in response.text
        assert "maxlength=\"23\"" in response.text
        assert "maxlength=\"5\"" in response.text
        assert "maxlength=\"4\"" in response.text

    def test_pg_url_displays_preselected_card_brand(self):
        with TestClient(app) as client:
            response = client.get(
                "/pg/card-register",
                params={"order_id": VALID_ORDER_ID, "card_brand": "KB국민"},
            )

        assert response.status_code == 200
        assert "KB국민" in response.text

    def test_card_verification_success_returns_billing_key(
        self,
        api_client_with_success_service_stub,
    ):
        response = api_client_with_success_service_stub.post(
            "/card-register",
            json=valid_registration_payload(),
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "success",
            "billing_key": VALID_BILLING_KEY,
        }

    def test_openapi_prefixed_path_returns_billing_key(
        self,
        api_client_with_success_service_stub,
    ):
        response = api_client_with_success_service_stub.post(
            "/pg/card-register",
            json=valid_registration_payload(),
        )

        assert response.status_code == 200
        assert response.json()["billing_key"] == VALID_BILLING_KEY

    def test_duplicate_order_id_returns_existing_billing_key(
        self,
        api_client_with_success_service_stub,
    ):
        first_response = api_client_with_success_service_stub.post(
            "/card-register",
            json=valid_registration_payload(),
        )
        second_response = api_client_with_success_service_stub.post(
            "/card-register",
            json=valid_registration_payload(),
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["billing_key"] == VALID_BILLING_KEY

    def test_card_verification_failure_returns_failed_without_billing_key(
        self,
        api_client_with_failed_service_stub,
    ):
        response = api_client_with_failed_service_stub.post(
            "/card-register",
            json=valid_registration_payload(),
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "failed",
            "billing_key": None,
        }

    def test_missing_order_id_returns_422(self, api_client_with_success_service_stub):
        payload = valid_registration_payload()
        payload.pop("order_id")

        response = api_client_with_success_service_stub.post(
            "/card-register",
            json=payload,
        )

        assert response.status_code == 422
