"""
앱 access token 재발급 API 테스트.
UC-AUTH-006: POST /auth/refresh
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_refresh_access_token_service
from app.application.auth.refresh_access_token import RefreshAccessTokenResult
from app.main import app


VALID_REFRESH_TOKEN = "app-refresh-001"
VALID_APP_ACCESS_TOKEN = "app-access-new-001"


class StubRefreshAccessTokenService:
    def execute(self, command):
        return RefreshAccessTokenResult(app_access_token=VALID_APP_ACCESS_TOKEN)


class StubRefreshAccessTokenServiceThatRaises:
    def __init__(self, error_code: str):
        self.error_code = error_code

    def execute(self, command):
        raise ValueError(self.error_code)


@pytest.fixture
def api_client_with_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_refresh_access_token_service] = (
        lambda: StubRefreshAccessTokenService()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


def make_client_with_failing_service(error_code: str):
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_refresh_access_token_service] = (
        lambda: StubRefreshAccessTokenServiceThatRaises(error_code)
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_missing_token_stub():
    yield from make_client_with_failing_service("refresh_token_not_found")


@pytest.fixture
def api_client_with_expired_token_stub():
    yield from make_client_with_failing_service("refresh_token_expired")


@pytest.fixture
def api_client_with_revoked_token_stub():
    yield from make_client_with_failing_service("refresh_token_revoked")


class TestRefreshAccessTokenApi:
    """UC-AUTH-006 - POST /auth/refresh"""

    def test_active_refresh_token_returns_200_with_new_access_token(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.post(
            "/auth/refresh",
            json={"refresh_token": VALID_REFRESH_TOKEN},
        )

        assert response.status_code == 200
        assert response.json()["app_access_token"] == VALID_APP_ACCESS_TOKEN
        assert response.json()["app_refresh_token"] is None

    def test_missing_refresh_token_returns_422(self, api_client_with_service_stub):
        response = api_client_with_service_stub.post("/auth/refresh", json={})

        assert response.status_code == 422

    def test_refresh_token_not_found_returns_401(
        self,
        api_client_with_missing_token_stub,
    ):
        response = api_client_with_missing_token_stub.post(
            "/auth/refresh",
            json={"refresh_token": VALID_REFRESH_TOKEN},
        )

        assert response.status_code == 401
        assert response.json()["message"] == "refresh_token_not_found"

    def test_expired_refresh_token_returns_401(
        self,
        api_client_with_expired_token_stub,
    ):
        response = api_client_with_expired_token_stub.post(
            "/auth/refresh",
            json={"refresh_token": VALID_REFRESH_TOKEN},
        )

        assert response.status_code == 401
        assert response.json()["message"] == "refresh_token_expired"

    def test_revoked_refresh_token_returns_401(
        self,
        api_client_with_revoked_token_stub,
    ):
        response = api_client_with_revoked_token_stub.post(
            "/auth/refresh",
            json={"refresh_token": VALID_REFRESH_TOKEN},
        )

        assert response.status_code == 401
        assert response.json()["message"] == "refresh_token_revoked"
