"""
LPR 출차 이벤트 API 테스트.
UC-PMS-005: POST /lpr/exit
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_handle_lpr_exit_service
from app.application.pms.handle_lpr_exit import HandleLprExitResult
from app.main import app


VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"
VALID_PMS_SESSION_ID = "pms-sess-001"


class StubHandleLprExitService:
    def __init__(self, status, pms_session_id=None):
        self.status = status
        self.pms_session_id = pms_session_id

    def execute(self, command):
        return HandleLprExitResult(
            status=self.status,
            pms_session_id=self.pms_session_id,
        )


def _override(service):
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_handle_lpr_exit_service] = lambda: service
    return original


@pytest.fixture
def api_client_opened():
    original = _override(StubHandleLprExitService(status="opened", pms_session_id=VALID_PMS_SESSION_ID))
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_not_paid():
    original = _override(StubHandleLprExitService(status="not_paid"))
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_not_found():
    original = _override(StubHandleLprExitService(status="not_found"))
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


def valid_exit_payload():
    return {"lot_id": VALID_LOT_ID, "plate": VALID_PLATE}


class TestHandleLprExitApi:
    """UC-PMS-005 - POST /lpr/exit"""

    def test_paid_session_returns_opened(self, api_client_opened):
        """결제 완료 차량은 status=opened와 pms_session_id를 반환한다."""
        response = api_client_opened.post("/lpr/exit", json=valid_exit_payload())

        assert response.status_code == 200
        assert response.json()["status"] == "opened"
        assert response.json()["pms_session_id"] == VALID_PMS_SESSION_ID

    def test_unpaid_session_returns_not_paid(self, api_client_not_paid):
        """미결제 차량은 status=not_paid를 반환한다."""
        response = api_client_not_paid.post("/lpr/exit", json=valid_exit_payload())

        assert response.status_code == 200
        assert response.json()["status"] == "not_paid"

    def test_unknown_plate_returns_not_found(self, api_client_not_found):
        """세션이 없는 번호판은 status=not_found를 반환한다."""
        response = api_client_not_found.post("/lpr/exit", json=valid_exit_payload())

        assert response.status_code == 200
        assert response.json()["status"] == "not_found"

    def test_missing_plate_returns_422(self, api_client_opened):
        """plate 누락 시 422를 반환한다."""
        response = api_client_opened.post("/lpr/exit", json={"lot_id": VALID_LOT_ID})

        assert response.status_code == 422
