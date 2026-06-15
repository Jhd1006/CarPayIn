"""
제휴 주차장 길안내 사전 등록 API 테스트.
UC-PARK-001: POST /parking/navigate
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_register_pre_notify_service
from app.application.parking.register_pre_notify import RegisterPreNotifyResult
from app.main import app


VALID_ACCESS_TOKEN = "at-valid-token-001"
VALID_CAR_ID = "car-001"
VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"
AUTH_HEADERS = {"Authorization": f"Bearer {VALID_ACCESS_TOKEN}"}


class StubRegisterPreNotifyService:
    def execute(self, command):
        return RegisterPreNotifyResult(
            status="registered",
            car_id=VALID_CAR_ID,
            lot_id=command.lot_id,
            plate=VALID_PLATE,
        )


class StubRegisterPreNotifyServiceThatFails:
    def __init__(self, error_code: str):
        self.error_code = error_code

    def execute(self, command):
        raise ValueError(self.error_code)


@pytest.fixture
def api_client_with_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_register_pre_notify_service] = (
        lambda: StubRegisterPreNotifyService()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_no_billing_key_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_register_pre_notify_service] = (
        lambda: StubRegisterPreNotifyServiceThatFails("no_active_billing_key")
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_plate_missing_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_register_pre_notify_service] = (
        lambda: StubRegisterPreNotifyServiceThatFails("plate_not_registered")
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_pms_failure_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_register_pre_notify_service] = (
        lambda: StubRegisterPreNotifyServiceThatFails("pms_pre_register_failed")
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


class TestRegisterPreNotifyApi:
    """UC-PARK-001 - POST /parking/navigate"""

    def test_valid_request_returns_200_with_registered_status(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.post(
            "/parking/navigate",
            headers=AUTH_HEADERS,
            json={"lot_id": VALID_LOT_ID},
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "registered",
            "car_id": VALID_CAR_ID,
            "lot_id": VALID_LOT_ID,
            "plate": VALID_PLATE,
        }

    def test_missing_bearer_token_returns_401(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.post(
            "/parking/navigate",
            json={"lot_id": VALID_LOT_ID},
        )

        assert response.status_code == 401

    def test_missing_lot_id_returns_422(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.post(
            "/parking/navigate",
            headers=AUTH_HEADERS,
            json={},
        )

        assert response.status_code == 422

    def test_no_active_billing_key_returns_400(
        self,
        api_client_with_no_billing_key_service_stub,
    ):
        response = api_client_with_no_billing_key_service_stub.post(
            "/parking/navigate",
            headers=AUTH_HEADERS,
            json={"lot_id": VALID_LOT_ID},
        )

        assert response.status_code == 400
        assert response.json()["message"] == "no_active_billing_key"

    def test_plate_not_registered_returns_400(
        self,
        api_client_with_plate_missing_service_stub,
    ):
        response = api_client_with_plate_missing_service_stub.post(
            "/parking/navigate",
            headers=AUTH_HEADERS,
            json={"lot_id": VALID_LOT_ID},
        )

        assert response.status_code == 400
        assert response.json()["message"] == "plate_not_registered"

    def test_pms_pre_register_failure_returns_400(
        self,
        api_client_with_pms_failure_service_stub,
    ):
        response = api_client_with_pms_failure_service_stub.post(
            "/parking/navigate",
            headers=AUTH_HEADERS,
            json={"lot_id": VALID_LOT_ID},
        )

        assert response.status_code == 400
        assert response.json()["message"] == "pms_pre_register_failed"
