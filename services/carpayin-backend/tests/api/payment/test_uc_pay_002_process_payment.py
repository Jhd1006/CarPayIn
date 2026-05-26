"""
결제 요청 API 테스트
UC-PAY-002: POST /payment
UC-PAY-003: PMS 결제 완료 통보는 UC-PAY-002 성공 흐름 안에서 함께 검증한다
            (outbound call이므로 별도 inbound endpoint 없음)
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_process_payment_service
from app.application.payment.process_payment import ProcessPaymentResult
from app.main import app


VALID_ACCESS_TOKEN = "at-valid-token-001"
VALID_SESSION_ID = "parking-session-001"
VALID_TX_ID = "tx-abc-001"
VALID_AMOUNT = 5000
VALID_CURRENCY = "KRW"
VALID_APPROVAL_NO = "APPR123456"

AUTH_HEADERS = {"Authorization": f"Bearer {VALID_ACCESS_TOKEN}"}


class StubProcessPaymentService:
    def execute(self, command):
        return ProcessPaymentResult(
            status="success",
            tx_id=VALID_TX_ID,
            session_id=command.session_id,
            approval_no=VALID_APPROVAL_NO,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )


class StubProcessPaymentServiceThatReturnsFailed:
    def execute(self, command):
        return ProcessPaymentResult(
            status="failed",
            tx_id=VALID_TX_ID,
            session_id=command.session_id,
            failed_reason="PG payment declined",
        )


class StubProcessPaymentServiceThatRaises:
    def __init__(self, error_code: str):
        self.error_code = error_code

    def execute(self, command):
        raise ValueError(self.error_code)


@pytest.fixture
def api_client_with_service_stub():
    """서비스만 stub, auth 미적용 (401 테스트용)"""
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_process_payment_service] = (
        lambda: StubProcessPaymentService()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_success_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_process_payment_service] = (
        lambda: StubProcessPaymentService()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_pg_failure_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_process_payment_service] = (
        lambda: StubProcessPaymentServiceThatReturnsFailed()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_quote_not_found_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_process_payment_service] = (
        lambda: StubProcessPaymentServiceThatRaises("quote_not_found")
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_amount_mismatch_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_process_payment_service] = (
        lambda: StubProcessPaymentServiceThatRaises("amount_currency_mismatch")
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_session_not_found_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_process_payment_service] = (
        lambda: StubProcessPaymentServiceThatRaises("session_not_found")
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_car_mismatch_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_process_payment_service] = (
        lambda: StubProcessPaymentServiceThatRaises("session_car_id_mismatch")
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_no_billing_key_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_process_payment_service] = (
        lambda: StubProcessPaymentServiceThatRaises("no_active_billing_key")
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


class TestProcessPaymentApi:
    """UC-PAY-002 - POST /payment"""

    def test_valid_request_returns_200_on_pg_success(
        self, api_client_with_success_stub
    ):
        response = api_client_with_success_stub.post(
            "/payment",
            headers=AUTH_HEADERS,
            json={
                "session_id": VALID_SESSION_ID,
                "amount": VALID_AMOUNT,
                "currency": VALID_CURRENCY,
            },
        )

        assert response.status_code == 200

        body = response.json()
        assert "status" in body
        assert body["status"] == "success"
        assert "tx_id" in body
        assert "approval_no" in body
        assert body["approval_no"] == VALID_APPROVAL_NO
        assert "amount" in body
        assert body["amount"] == VALID_AMOUNT
        assert "currency" in body
        assert body["currency"] == VALID_CURRENCY

    def test_pg_failure_returns_402(self, api_client_with_pg_failure_stub):
        response = api_client_with_pg_failure_stub.post(
            "/payment",
            headers=AUTH_HEADERS,
            json={
                "session_id": VALID_SESSION_ID,
                "amount": VALID_AMOUNT,
                "currency": VALID_CURRENCY,
            },
        )

        assert response.status_code == 402

        body = response.json()
        assert "status" in body
        assert body["status"] == "failed"
        assert "tx_id" in body
        assert "failed_reason" in body

    def test_missing_bearer_token_returns_401(self, api_client_with_service_stub):
        response = api_client_with_service_stub.post(
            "/payment",
            json={
                "session_id": VALID_SESSION_ID,
                "amount": VALID_AMOUNT,
                "currency": VALID_CURRENCY,
            },
        )

        assert response.status_code == 401

    def test_missing_session_id_returns_422(self, api_client_with_success_stub):
        response = api_client_with_success_stub.post(
            "/payment",
            headers=AUTH_HEADERS,
            json={
                "amount": VALID_AMOUNT,
                "currency": VALID_CURRENCY,
            },
        )

        assert response.status_code == 422

    def test_missing_amount_returns_422(self, api_client_with_success_stub):
        response = api_client_with_success_stub.post(
            "/payment",
            headers=AUTH_HEADERS,
            json={
                "session_id": VALID_SESSION_ID,
                "currency": VALID_CURRENCY,
            },
        )

        assert response.status_code == 422

    def test_quote_not_found_returns_409(self, api_client_with_quote_not_found_stub):
        response = api_client_with_quote_not_found_stub.post(
            "/payment",
            headers=AUTH_HEADERS,
            json={
                "session_id": VALID_SESSION_ID,
                "amount": VALID_AMOUNT,
                "currency": VALID_CURRENCY,
            },
        )

        assert response.status_code == 409
        assert response.json()["message"] == "quote_not_found"

    def test_amount_currency_mismatch_returns_409(
        self, api_client_with_amount_mismatch_stub
    ):
        response = api_client_with_amount_mismatch_stub.post(
            "/payment",
            headers=AUTH_HEADERS,
            json={
                "session_id": VALID_SESSION_ID,
                "amount": VALID_AMOUNT,
                "currency": VALID_CURRENCY,
            },
        )

        assert response.status_code == 409
        assert response.json()["message"] == "amount_currency_mismatch"

    def test_session_car_id_mismatch_returns_403(self, api_client_with_car_mismatch_stub):
        response = api_client_with_car_mismatch_stub.post(
            "/payment",
            headers=AUTH_HEADERS,
            json={
                "session_id": VALID_SESSION_ID,
                "amount": VALID_AMOUNT,
                "currency": VALID_CURRENCY,
            },
        )

        assert response.status_code == 403
        assert response.json()["message"] == "session_car_id_mismatch"

    def test_session_not_found_returns_400(self, api_client_with_session_not_found_stub):
        response = api_client_with_session_not_found_stub.post(
            "/payment",
            headers=AUTH_HEADERS,
            json={
                "session_id": VALID_SESSION_ID,
                "amount": VALID_AMOUNT,
                "currency": VALID_CURRENCY,
            },
        )

        assert response.status_code == 400
        assert response.json()["message"] == "session_not_found"

    def test_no_active_billing_key_returns_400(
        self, api_client_with_no_billing_key_stub
    ):
        response = api_client_with_no_billing_key_stub.post(
            "/payment",
            headers=AUTH_HEADERS,
            json={
                "session_id": VALID_SESSION_ID,
                "amount": VALID_AMOUNT,
                "currency": VALID_CURRENCY,
            },
        )

        assert response.status_code == 400
        assert response.json()["message"] == "no_active_billing_key"
