"""
차량번호 사전 등록 API 테스트.
UC-PMS-001: POST /parking/pre-register
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_register_pre_notify_service
from app.application.pms.register_pre_notify import RegisterPreNotifyResult
from app.main import app


VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"


class StubRegisterPreNotifyService:
    def execute(self, command):
        return RegisterPreNotifyResult(
            status="registered",
            lot_id=command.lot_id,
            plate=command.plate,
        )


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


class TestRegisterPreNotifyApi:
    """UC-PMS-001 - POST /parking/pre-register"""

    def test_valid_plate_returns_registered(self, api_client_with_service_stub):
        response = api_client_with_service_stub.post(
            "/parking/pre-register",
            json={"lot_id": VALID_LOT_ID, "plate": VALID_PLATE},
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "registered",
            "lot_id": VALID_LOT_ID,
            "plate": VALID_PLATE,
        }

    def test_duplicate_request_is_idempotent(self, api_client_with_service_stub):
        first_response = api_client_with_service_stub.post(
            "/parking/pre-register",
            json={"lot_id": VALID_LOT_ID, "plate": VALID_PLATE},
        )
        second_response = api_client_with_service_stub.post(
            "/parking/pre-register",
            json={"lot_id": VALID_LOT_ID, "plate": VALID_PLATE},
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["status"] == "registered"

    def test_missing_plate_returns_422(self, api_client_with_service_stub):
        response = api_client_with_service_stub.post(
            "/parking/pre-register",
            json={"lot_id": VALID_LOT_ID},
        )

        assert response.status_code == 422
