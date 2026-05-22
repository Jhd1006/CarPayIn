"""
현대 OAuth 로그인 시작 API 테스트.
UC-AUTH-002: GET /auth/hyundai/start?session_id={session_id}
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_start_hyundai_oauth_service
from app.application.auth.start_hyundai_oauth import StartHyundaiOAuthResult
from app.main import app


VALID_SESSION_ID = "sess-001"
VALID_REDIRECT_URL = "https://accounts.hyundai.test/oauth2/authorize?state=oauth-001"


class StubStartHyundaiOAuthService:
    def execute(self, command):
        return StartHyundaiOAuthResult(redirect_url=VALID_REDIRECT_URL)


class StubStartHyundaiOAuthServiceThatFails:
    def execute(self, command):
        raise ValueError("qr_session_not_found")


@pytest.fixture
def api_client_with_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_start_hyundai_oauth_service] = (
        lambda: StubStartHyundaiOAuthService()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_failing_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_start_hyundai_oauth_service] = (
        lambda: StubStartHyundaiOAuthServiceThatFails()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


class TestStartHyundaiOAuthApi:
    """UC-AUTH-002 - GET /auth/hyundai/start?session_id={session_id}"""

    def test_pending_qr_session_returns_302_redirect(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.get(
            "/auth/hyundai/start",
            params={"session_id": VALID_SESSION_ID},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["location"] == VALID_REDIRECT_URL

    def test_missing_session_id_returns_422(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.get(
            "/auth/hyundai/start",
            follow_redirects=False,
        )

        assert response.status_code == 422

    def test_invalid_qr_session_returns_400(
        self,
        api_client_with_failing_service_stub,
    ):
        response = api_client_with_failing_service_stub.get(
            "/auth/hyundai/start",
            params={"session_id": VALID_SESSION_ID},
            follow_redirects=False,
        )

        assert response.status_code == 400
        assert response.json()["message"] == "qr_session_not_found"
