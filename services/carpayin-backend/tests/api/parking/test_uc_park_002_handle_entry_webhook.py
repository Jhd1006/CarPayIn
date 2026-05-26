"""
PMS 입차 webhook 처리 API 테스트.
UC-PARK-002: POST /webhook/entry
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_handle_entry_webhook_service
from app.application.parking.handle_entry_webhook import HandleEntryWebhookResult
from app.main import app


VALID_PMS_SIGNATURE = "valid-pms-signature"
VALID_PMS_SESSION_ID = "pms-sess-001"
VALID_SESSION_ID = "parking-session-001"
EXISTING_SESSION_ID = "parking-session-existing"
VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"
VALID_ENTRY_TIME = "2026-05-20T14:30:00"
PMS_HEADERS = {"X-PMS-Signature": VALID_PMS_SIGNATURE}


class StubHandleEntryWebhookService:
    def __init__(self, *, status: str = "confirmed", session_id: str | None = None):
        self.status = status
        self.session_id = session_id

    def execute(self, command):
        return HandleEntryWebhookResult(
            status=self.status,
            session_id=self.session_id,
        )


class StubHandleEntryWebhookServiceThatFails:
    def __init__(self, error_code: str):
        self.error_code = error_code

    def execute(self, command):
        raise ValueError(self.error_code)


@pytest.fixture
def api_client_with_confirmed_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_handle_entry_webhook_service] = (
        lambda: StubHandleEntryWebhookService(
            status="confirmed",
            session_id=VALID_SESSION_ID,
        )
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_not_registered_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_handle_entry_webhook_service] = (
        lambda: StubHandleEntryWebhookService(
            status="not_registered",
            session_id=None,
        )
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_existing_session_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_handle_entry_webhook_service] = (
        lambda: StubHandleEntryWebhookService(
            status="confirmed",
            session_id=EXISTING_SESSION_ID,
        )
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_pms_auth_failure_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_handle_entry_webhook_service] = (
        lambda: StubHandleEntryWebhookServiceThatFails("pms_auth_failed")
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_invalid_entry_time_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_handle_entry_webhook_service] = (
        lambda: StubHandleEntryWebhookServiceThatFails("invalid_entry_time_format")
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


def valid_entry_payload():
    return {
        "pms_session_id": VALID_PMS_SESSION_ID,
        "lot_id": VALID_LOT_ID,
        "plate": VALID_PLATE,
        "entry_time": VALID_ENTRY_TIME,
    }


class TestHandleEntryWebhookApi:
    """UC-PARK-002 - POST /webhook/entry"""

    def test_pre_notify_exists_returns_200_with_confirmed_status(
        self,
        api_client_with_confirmed_service_stub,
    ):
        response = api_client_with_confirmed_service_stub.post(
            "/webhook/entry",
            headers=PMS_HEADERS,
            json=valid_entry_payload(),
        )

        assert response.status_code == 200
        body = response.json()
        assert "status" in body 
        assert body["status"] == "confirmed"
        assert body["session_id"] == VALID_SESSION_ID
        assert body["lot_id"] == VALID_LOT_ID
        assert body["entry_time"] == VALID_ENTRY_TIME

    def test_pre_notify_missing_returns_200_with_not_registered_status(
        self,
        api_client_with_not_registered_service_stub,
    ):
        response = api_client_with_not_registered_service_stub.post(
            "/webhook/entry",
            headers=PMS_HEADERS,
            json=valid_entry_payload(),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "not_registered"
        assert response.json()["session_id"] is None

    def test_duplicate_or_active_session_returns_existing_confirmed_result(
        self,
        api_client_with_existing_session_service_stub,
    ):
        response = api_client_with_existing_session_service_stub.post(
            "/webhook/entry",
            headers=PMS_HEADERS,
            json=valid_entry_payload(),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "confirmed"
        assert response.json()["session_id"] == EXISTING_SESSION_ID

    def test_missing_pms_signature_returns_422(
        self,
        api_client_with_confirmed_service_stub,
    ):
        response = api_client_with_confirmed_service_stub.post(
            "/webhook/entry",
            json=valid_entry_payload(),
        )

        assert response.status_code == 422

    def test_pms_auth_failure_returns_401(
        self,
        api_client_with_pms_auth_failure_service_stub,
    ):
        response = api_client_with_pms_auth_failure_service_stub.post(
            "/webhook/entry",
            headers=PMS_HEADERS,
            json=valid_entry_payload(),
        )

        assert response.status_code == 401
        assert response.json()["message"] == "pms_auth_failed"

    def test_missing_pms_session_id_returns_422(
        self,
        api_client_with_confirmed_service_stub,
    ):
        payload = valid_entry_payload()
        payload.pop("pms_session_id")

        response = api_client_with_confirmed_service_stub.post(
            "/webhook/entry",
            headers=PMS_HEADERS,
            json=payload,
        )

        assert response.status_code == 422

    def test_invalid_entry_time_returns_400(
        self,
        api_client_with_invalid_entry_time_service_stub,
    ):
        payload = valid_entry_payload()
        payload["entry_time"] = "invalid-time-format"

        response = api_client_with_invalid_entry_time_service_stub.post(
            "/webhook/entry",
            headers=PMS_HEADERS,
            json=payload,
        )

        assert response.status_code == 400
        assert response.json()["message"] == "invalid_entry_time_format"
