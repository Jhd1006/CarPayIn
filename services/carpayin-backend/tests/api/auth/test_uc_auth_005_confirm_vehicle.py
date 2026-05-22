"""
차량 선택 확정과 앱 토큰 발급 API 테스트.
UC-AUTH-005: POST /auth/confirm-car
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_confirm_vehicle_service
from app.application.auth.confirm_vehicle import ConfirmVehicleResult
from app.main import app


VALID_TEMP_ACCESS_TOKEN = "temp-access-001"
VALID_APP_ACCESS_TOKEN = "app-access-001"
VALID_APP_REFRESH_TOKEN = "app-refresh-001"
VALID_USER_ID = "hyundai-user-001"
VALID_USER_NAME = "홍길동"
VALID_CAR_ID = "hyundai-car-001"
VALID_VIN_HASH = "vin-hash-001"
VALID_CAR = {
    "car_id": VALID_CAR_ID,
    "car_sellname": "아이오닉 6",
    "plate": "12가 3456",
}
AUTH_HEADERS = {"Authorization": f"Bearer {VALID_TEMP_ACCESS_TOKEN}"}


class StubConfirmVehicleService:
    def execute(self, command):
        return ConfirmVehicleResult(
            app_access_token=VALID_APP_ACCESS_TOKEN,
            app_refresh_token=VALID_APP_REFRESH_TOKEN,
            user_id=VALID_USER_ID,
            name=VALID_USER_NAME,
            car_id=command.car_id,
            car=VALID_CAR,
        )


class StubConfirmVehicleServiceThatRaises:
    def __init__(self, error_code: str):
        self.error_code = error_code

    def execute(self, command):
        raise ValueError(self.error_code)


@pytest.fixture
def api_client_with_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_confirm_vehicle_service] = (
        lambda: StubConfirmVehicleService()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


def make_client_with_failing_service(error_code: str):
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_confirm_vehicle_service] = (
        lambda: StubConfirmVehicleServiceThatRaises(error_code)
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_expired_temp_token_stub():
    yield from make_client_with_failing_service("temp_token_expired")


@pytest.fixture
def api_client_with_car_not_in_list_stub():
    yield from make_client_with_failing_service("car_id_not_in_list")


@pytest.fixture
def api_client_with_vin_mismatch_stub():
    yield from make_client_with_failing_service("vin_hash_mismatch")


class TestConfirmVehicleApi:
    """UC-AUTH-005 - POST /auth/confirm-car"""

    def test_valid_request_returns_200_with_app_tokens(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.post(
            "/auth/confirm-car",
            headers=AUTH_HEADERS,
            json={
                "car_id": VALID_CAR_ID,
                "vin_hash": VALID_VIN_HASH,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["app_access_token"] == VALID_APP_ACCESS_TOKEN
        assert body["app_refresh_token"] == VALID_APP_REFRESH_TOKEN
        assert body["user_id"] == VALID_USER_ID
        assert body["name"] == VALID_USER_NAME
        assert body["car_id"] == VALID_CAR_ID
        assert body["car"] == VALID_CAR

    def test_missing_temp_token_returns_401(self, api_client_with_service_stub):
        response = api_client_with_service_stub.post(
            "/auth/confirm-car",
            json={
                "car_id": VALID_CAR_ID,
                "vin_hash": VALID_VIN_HASH,
            },
        )

        assert response.status_code == 401

    def test_missing_car_id_returns_422(self, api_client_with_service_stub):
        response = api_client_with_service_stub.post(
            "/auth/confirm-car",
            headers=AUTH_HEADERS,
            json={"vin_hash": VALID_VIN_HASH},
        )

        assert response.status_code == 422

    def test_expired_temp_token_returns_401(
        self,
        api_client_with_expired_temp_token_stub,
    ):
        response = api_client_with_expired_temp_token_stub.post(
            "/auth/confirm-car",
            headers=AUTH_HEADERS,
            json={
                "car_id": VALID_CAR_ID,
                "vin_hash": VALID_VIN_HASH,
            },
        )

        assert response.status_code == 401
        assert response.json()["message"] == "temp_token_expired"

    def test_car_id_not_in_list_returns_400(
        self,
        api_client_with_car_not_in_list_stub,
    ):
        response = api_client_with_car_not_in_list_stub.post(
            "/auth/confirm-car",
            headers=AUTH_HEADERS,
            json={
                "car_id": VALID_CAR_ID,
                "vin_hash": VALID_VIN_HASH,
            },
        )

        assert response.status_code == 400
        assert response.json()["message"] == "car_id_not_in_list"

    def test_vin_hash_mismatch_returns_400(
        self,
        api_client_with_vin_mismatch_stub,
    ):
        response = api_client_with_vin_mismatch_stub.post(
            "/auth/confirm-car",
            headers=AUTH_HEADERS,
            json={
                "car_id": VALID_CAR_ID,
                "vin_hash": VALID_VIN_HASH,
            },
        )

        assert response.status_code == 400
        assert response.json()["message"] == "vin_hash_mismatch"
