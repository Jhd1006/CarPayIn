"""
현대 OAuth callback 처리 API 테스트.
UC-AUTH-003: GET /auth/redirect
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_handle_hyundai_oauth_callback_service
from app.application.auth.handle_hyundai_oauth_callback import (
    HandleHyundaiOAuthCallbackResult,
)
from app.main import app


VALID_CODE = "hyundai-code-001"
VALID_OAUTH_STATE = "oauth-state-001"
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


class StubHandleHyundaiOAuthCallbackService:
    def execute(self, command):
        return HandleHyundaiOAuthCallbackResult(
            status="complete",
            session_id=VALID_SESSION_ID,
            user_id=VALID_USER_ID,
            name=VALID_USER_NAME,
            cars=VALID_CARS,
            temp_access_token=VALID_TEMP_ACCESS_TOKEN,
        )


class StubHandleHyundaiOAuthCallbackServiceThatFails:
    def execute(self, command):
        raise ValueError("oauth_state_not_found")


@pytest.fixture
def api_client_with_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_handle_hyundai_oauth_callback_service] = (
        lambda: StubHandleHyundaiOAuthCallbackService()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_failing_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_handle_hyundai_oauth_callback_service] = (
        lambda: StubHandleHyundaiOAuthCallbackServiceThatFails()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


class TestHandleHyundaiOAuthCallbackApi:
    """UC-AUTH-003 - GET /auth/redirect"""

    def test_valid_callback_returns_200_with_session_status(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.get(
            "/auth/redirect",
            params={
                "code": VALID_CODE,
                "state": VALID_OAUTH_STATE,
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "complete",
            "session_id": VALID_SESSION_ID,
        }

    def test_missing_code_returns_422(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.get(
            "/auth/redirect",
            params={"state": VALID_OAUTH_STATE},
        )

        assert response.status_code == 422

    def test_missing_state_returns_422(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.get(
            "/auth/redirect",
            params={"code": VALID_CODE},
        )

        assert response.status_code == 422

    def test_invalid_state_returns_400(
        self,
        api_client_with_failing_service_stub,
    ):
        response = api_client_with_failing_service_stub.get(
            "/auth/redirect",
            params={
                "code": VALID_CODE,
                "state": VALID_OAUTH_STATE,
            },
        )

        assert response.status_code == 400
        assert response.json()["message"] == "oauth_state_not_found"
