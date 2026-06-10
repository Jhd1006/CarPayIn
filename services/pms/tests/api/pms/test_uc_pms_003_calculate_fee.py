"""
현재 요금 계산 API 테스트.
UC-PMS-003: GET /parking/fee
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_calculate_fee_service
from app.application.pms.calculate_fee import CalculateFeeResult
from app.main import app


VALID_PMS_SESSION_ID = "pms-sess-001"
VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"
VALID_ENTRY_TIME = "2026-05-20T14:30:00"
VALID_CURRENT_TIME = "2026-05-20T15:30:00"


class StubCalculateFeeService:
    def execute(self, command):
        return CalculateFeeResult(
            amount=5000,
            duration_minutes=60,
            currency="KRW",
            pms_session_id=VALID_PMS_SESSION_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
            calculated_at=VALID_CURRENT_TIME,
        )


class StubCalculateFeeServiceThatFails:
    def execute(self, command):
        raise ValueError("session_not_found")


@pytest.fixture
def api_client_with_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_calculate_fee_service] = (
        lambda: StubCalculateFeeService()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_failing_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_calculate_fee_service] = (
        lambda: StubCalculateFeeServiceThatFails()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


class TestCalculateFeeApi:
    """UC-PMS-003 - GET /parking/fee"""

    def test_active_session_returns_amount_and_duration(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.get(
            "/parking/fee",
            params={
                "pms_session_id": VALID_PMS_SESSION_ID,
                "current_time": VALID_CURRENT_TIME,
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "pms_session_id": VALID_PMS_SESSION_ID,
            "lot_id": VALID_LOT_ID,
            "plate": VALID_PLATE,
            "amount": 5000,
            "duration_minutes": 60,
            "currency": "KRW",
            "entry_time": VALID_ENTRY_TIME,
            "calculated_at": VALID_CURRENT_TIME,
        }

    def test_session_not_found_returns_404(
        self,
        api_client_with_failing_service_stub,
    ):
        response = api_client_with_failing_service_stub.get(
            "/parking/fee",
            params={
                "lot_id": VALID_LOT_ID,
                "plate": VALID_PLATE,
            },
        )

        assert response.status_code == 404
        assert response.json()["message"] == "session_not_found"
