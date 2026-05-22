"""
로그인 세션 상태 조회 API 테스트.
UC-AUTH-004: GET /auth/session/{session_id}/status
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_login_session_status_service
from app.application.auth.get_login_session_status import (
    GetLoginSessionStatusResult,
)
from app.main import app


VALID_SESSION_ID = "sess-001"
VALID_USER_ID = "hyundai-user-001"
VALID_USER_NAME = "홍길동"
VALID_TEMP_ACCESS_TOKEN = "temp-access-001"
VALID_CARS = [
    {
        "car_id": "hyundai-car-001",
        "car_sellname": "아이오닉 6",
        "plate": "12가 3456",
    }
]


class StubGetLoginSessionStatusService:
    def execute(self, command):
        return GetLoginSessionStatusResult(status="pending")


class StubGetLoginSessionStatusServiceComplete:
    def execute(self, command):
        return GetLoginSessionStatusResult(
            status="complete",
            user_id=VALID_USER_ID,
            name=VALID_USER_NAME,
            cars=VALID_CARS,
            temp_access_token=VALID_TEMP_ACCESS_TOKEN,
        )


class StubGetLoginSessionStatusServiceThatFails:
    def execute(self, command):
        raise ValueError("session_not_found")


@pytest.fixture
def api_client_with_pending_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_login_session_status_service] = (
        lambda: StubGetLoginSessionStatusService()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_complete_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_login_session_status_service] = (
        lambda: StubGetLoginSessionStatusServiceComplete()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_failing_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_login_session_status_service] = (
        lambda: StubGetLoginSessionStatusServiceThatFails()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


class TestGetLoginSessionStatusApi:
    """UC-AUTH-004 - GET /auth/session/{session_id}/status"""

    def test_pending_session_returns_200_with_pending_status(
        self,
        api_client_with_pending_service_stub,
    ):
        response = api_client_with_pending_service_stub.get(
            f"/auth/session/{VALID_SESSION_ID}/status",
        )

        assert response.status_code == 200
        assert response.json()["status"] == "pending"
        assert response.json()["user_id"] is None
        assert response.json()["cars"] is None

    def test_complete_session_returns_200_with_user_and_cars(
        self,
        api_client_with_complete_service_stub,
    ):
        response = api_client_with_complete_service_stub.get(
            f"/auth/session/{VALID_SESSION_ID}/status",
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "complete"
        assert body["user_id"] == VALID_USER_ID
        assert body["name"] == VALID_USER_NAME
        assert body["cars"] == VALID_CARS
        assert body["temp_access_token"] == VALID_TEMP_ACCESS_TOKEN

    def test_missing_session_returns_404(
        self,
        api_client_with_failing_service_stub,
    ):
        response = api_client_with_failing_service_stub.get(
            f"/auth/session/{VALID_SESSION_ID}/status",
        )

        assert response.status_code == 404
        assert response.json()["message"] == "session_not_found"
