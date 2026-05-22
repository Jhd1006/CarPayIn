"""
QR 로그인 세션 생성 API 테스트.
UC-AUTH-001: POST /auth/qr-session
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_create_qr_session_service
from app.application.auth.create_qr_session import CreateQrSessionResult
from app.main import app


VALID_SESSION_ID = "sess-001"
VALID_VIN_HASH = "vin-hash-001"
VALID_LOGIN_URL = (
    f"https://api.carpayin.test/auth/hyundai/start?session_id={VALID_SESSION_ID}"
)


class StubCreateQrSessionService:
    def execute(self, command):
        return CreateQrSessionResult(login_url=VALID_LOGIN_URL)


class StubCreateQrSessionServiceThatFails:
    def execute(self, command):
        raise ValueError("session_already_completed")


@pytest.fixture
def api_client_with_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_create_qr_session_service] = (
        lambda: StubCreateQrSessionService()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_failing_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_create_qr_session_service] = (
        lambda: StubCreateQrSessionServiceThatFails()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


class TestCreateQrSessionApi:
    """UC-AUTH-001 - POST /auth/qr-session"""

    def test_valid_request_returns_200_with_login_url(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.post(
            "/auth/qr-session",
            json={
                "login_session_id": VALID_SESSION_ID,
                "vin_hash": VALID_VIN_HASH,
            },
        )

        assert response.status_code == 200
        assert response.json()["login_url"] == VALID_LOGIN_URL

    def test_missing_login_session_id_returns_422(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.post(
            "/auth/qr-session",
            json={
                "vin_hash": VALID_VIN_HASH,
            },
        )

        assert response.status_code == 422

    def test_missing_vin_hash_returns_422(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.post(
            "/auth/qr-session",
            json={
                "login_session_id": VALID_SESSION_ID,
            },
        )

        assert response.status_code == 422

    def test_already_completed_session_returns_400(
        self,
        api_client_with_failing_service_stub,
    ):
        response = api_client_with_failing_service_stub.post(
            "/auth/qr-session",
            json={
                "login_session_id": VALID_SESSION_ID,
                "vin_hash": VALID_VIN_HASH,
            },
        )

        assert response.status_code == 400
        assert response.json()["code"] == "BAD_REQUEST"
        assert response.json()["message"] == "session_already_completed"
