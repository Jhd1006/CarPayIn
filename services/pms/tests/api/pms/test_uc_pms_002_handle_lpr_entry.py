"""
LPR 입차 이벤트 API 테스트.
UC-PMS-002: POST /lpr/entry
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_handle_lpr_entry_service
from app.application.pms.handle_lpr_entry import HandleLprEntryResult
from app.main import app


VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"
VALID_ENTRY_TIME = "2026-05-20T14:30:00"
VALID_PMS_SESSION_ID = "pms-sess-001"


class StubHandleLprEntryService:
    def __init__(self, status="created"):
        self.status = status

    def execute(self, command):
        return HandleLprEntryResult(
            status=self.status,
            pms_session_id=VALID_PMS_SESSION_ID,
        )


@pytest.fixture
def api_client_with_created_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_handle_lpr_entry_service] = (
        lambda: StubHandleLprEntryService(status="created")
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_existing_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_handle_lpr_entry_service] = (
        lambda: StubHandleLprEntryService(status="existing")
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


def valid_lpr_payload():
    return {
        "lot_id": VALID_LOT_ID,
        "plate": VALID_PLATE,
        "entry_time": VALID_ENTRY_TIME,
    }


class TestHandleLprEntryApi:
    """UC-PMS-002 - POST /lpr/entry"""

    def test_lpr_entry_returns_created_session(
        self,
        api_client_with_created_service_stub,
    ):
        response = api_client_with_created_service_stub.post(
            "/lpr/entry",
            json=valid_lpr_payload(),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "created"
        assert response.json()["pms_session_id"] == VALID_PMS_SESSION_ID

    def test_openapi_prefixed_path_returns_created_session(
        self,
        api_client_with_created_service_stub,
    ):
        response = api_client_with_created_service_stub.post(
            "/pms/lpr/entry",
            json=valid_lpr_payload(),
        )

        assert response.status_code == 200
        assert response.json()["pms_session_id"] == VALID_PMS_SESSION_ID

    def test_active_session_returns_existing_session(
        self,
        api_client_with_existing_service_stub,
    ):
        response = api_client_with_existing_service_stub.post(
            "/lpr/entry",
            json=valid_lpr_payload(),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "existing"
        assert response.json()["pms_session_id"] == VALID_PMS_SESSION_ID

    def test_missing_entry_time_returns_422(
        self,
        api_client_with_created_service_stub,
    ):
        payload = valid_lpr_payload()
        payload.pop("entry_time")

        response = api_client_with_created_service_stub.post(
            "/lpr/entry",
            json=payload,
        )

        assert response.status_code == 422
