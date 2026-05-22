"""
주차 요금 조회 API 테스트
UC-PAY-001: GET /fee/{session_id}
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_parking_fee_service
from app.application.payment.get_parking_fee import GetParkingFeeResult
from app.main import app


VALID_ACCESS_TOKEN = "at-valid-token-001"
VALID_SESSION_ID = "parking-session-001"
VALID_LOT_ID = "LOT_GN_01"
VALID_AMOUNT = 5000
VALID_DURATION = 90
VALID_CURRENCY = "KRW"
VALID_ENTRY_TIME = "2026-05-20T14:30:00"

AUTH_HEADERS = {"Authorization": f"Bearer {VALID_ACCESS_TOKEN}"}


class StubGetParkingFeeService:
    def execute(self, command):
        return GetParkingFeeResult(
            session_id=VALID_SESSION_ID,
            lot_id=VALID_LOT_ID,
            amount=VALID_AMOUNT,
            duration=VALID_DURATION,
            currency=VALID_CURRENCY,
            entry_time=VALID_ENTRY_TIME,
            status="active",
        )


class StubGetParkingFeeServiceThatRaises:
    def __init__(self, error_code: str):
        self.error_code = error_code

    def execute(self, command):
        raise ValueError(self.error_code)


class StubGetParkingFeeServiceThatRaisesPmsError:
    def execute(self, command):
        raise RuntimeError("pms_fee_query_failed")


@pytest.fixture
def api_client_with_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_parking_fee_service] = lambda: StubGetParkingFeeService()

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_car_mismatch_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_parking_fee_service] = (
        lambda: StubGetParkingFeeServiceThatRaises("session_car_id_mismatch")
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_session_not_found_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_parking_fee_service] = (
        lambda: StubGetParkingFeeServiceThatRaises("session_not_found")
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_session_not_active_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_parking_fee_service] = (
        lambda: StubGetParkingFeeServiceThatRaises("session_not_active")
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_pms_error_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_parking_fee_service] = (
        lambda: StubGetParkingFeeServiceThatRaisesPmsError()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


class TestGetParkingFeeApi:
    """UC-PAY-001 - GET /fee/{session_id}"""

    def test_valid_request_returns_200_with_fee_info(
        self, api_client_with_service_stub
    ):
        response = api_client_with_service_stub.get(
            f"/fee/{VALID_SESSION_ID}",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200

        body = response.json()
        assert body["session_id"] == VALID_SESSION_ID
        assert body["lot_id"] == VALID_LOT_ID
        assert body["amount"] == VALID_AMOUNT
        assert body["duration"] == VALID_DURATION
        assert body["currency"] == VALID_CURRENCY
        assert body["status"] == "active"

    def test_missing_bearer_token_returns_401(self, api_client_with_service_stub):
        response = api_client_with_service_stub.get(f"/fee/{VALID_SESSION_ID}")

        assert response.status_code == 401

    def test_session_car_id_mismatch_returns_403(
        self, api_client_with_car_mismatch_stub
    ):
        response = api_client_with_car_mismatch_stub.get(
            f"/fee/{VALID_SESSION_ID}",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 403
        assert response.json()["message"] == "session_car_id_mismatch"

    def test_session_not_found_returns_404(
        self, api_client_with_session_not_found_stub
    ):
        response = api_client_with_session_not_found_stub.get(
            f"/fee/{VALID_SESSION_ID}",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 404
        assert response.json()["message"] == "session_not_found"

    def test_session_not_active_returns_404(
        self, api_client_with_session_not_active_stub
    ):
        response = api_client_with_session_not_active_stub.get(
            f"/fee/{VALID_SESSION_ID}",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 404
        assert response.json()["message"] == "session_not_active"

    def test_pms_failure_returns_502(self, api_client_with_pms_error_stub):
        response = api_client_with_pms_error_stub.get(
            f"/fee/{VALID_SESSION_ID}",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 502
