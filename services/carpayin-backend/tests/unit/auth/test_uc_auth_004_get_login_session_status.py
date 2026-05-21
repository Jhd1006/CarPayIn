"""
QR 로그인 / 현대 OAuth 유스케이스 단위 테스트
UC-AUTH-004: 로그인 세션 상태 조회
"""

import pytest

from app.application.auth.get_login_session_status import (
    GetLoginSessionStatusCommand,
    GetLoginSessionStatusService,
)


VALID_SESSION_ID = "sess-001"
VALID_USER_ID = "hyundai-user-001"
VALID_USER_NAME = "홍길동"
VALID_TEMP_ACCESS_TOKEN = "temp-access-001"
EXPIRED_SESSION_ID = "sess-expired"
FAILED_SESSION_ID = "sess-failed"
INVALID_SESSION_ID = "sess-missing"
ERROR_SESSION_ID_REQUIRED = "session_id is required"
ERROR_SESSION_NOT_FOUND = "session_not_found"
ERROR_SESSION_EXPIRED = "session_expired"
ERROR_OAUTH_FAILED = "oauth_failed"
VALID_CARS = [
    {
        "car_id": "hyundai-car-001",
        "car_sellname": "아이오닉 6",
        "plate": "12가 3456",
    },
    {
        "car_id": "hyundai-car-002",
        "car_sellname": "쏘나타",
        "plate": "34나 7890",
    },
]


class FakeAppLoginResultStore:
    def __init__(self):
        self.results = {}
        self.get_result_calls = []

    def add_complete_result(self, session_id: str):
        self.results[session_id] = {
            "session_id": session_id,
            "status": "complete",
            "user_id": VALID_USER_ID,
            "name": VALID_USER_NAME,
            "cars": VALID_CARS,
            "temp_access_token": VALID_TEMP_ACCESS_TOKEN,
        }

    def add_failed_result(self, session_id: str):
        self.results[session_id] = {
            "session_id": session_id,
            "status": "failed",
        }

    def get_result(self, session_id: str):
        self.get_result_calls.append(session_id)
        return self.results.get(session_id)


class FakeQrSessionStore:
    def __init__(self):
        self.sessions = {}
        self.get_session_calls = []

    def add_session(self, *, session_id: str, status: str):
        self.sessions[session_id] = {
            "session_id": session_id,
            "status": status,
        }

    def get_session(self, session_id: str):
        self.get_session_calls.append(session_id)
        return self.sessions.get(session_id)


@pytest.fixture
def fake_app_login_result_store():
    return FakeAppLoginResultStore()


@pytest.fixture
def fake_qr_session_store():
    return FakeQrSessionStore()


@pytest.fixture
def get_login_session_status_service(
    fake_app_login_result_store,
    fake_qr_session_store,
):
    return GetLoginSessionStatusService(
        app_login_result_store=fake_app_login_result_store,
        qr_session_store=fake_qr_session_store,
    )


class TestGetLoginSessionStatus:
    """UC-AUTH-004 - GET /auth/session/{session_id}/status"""

    def test_pending_qr_session_returns_pending(
        self,
        get_login_session_status_service,
        fake_qr_session_store,
    ):
        """OAuth 완료 전이면 pending을 반환한다."""
        fake_qr_session_store.add_session(
            session_id=VALID_SESSION_ID,
            status="pending",
        )
        command = GetLoginSessionStatusCommand(session_id=VALID_SESSION_ID)

        result = get_login_session_status_service.execute(command)

        assert result.status == "pending"
        assert result.user_id is None
        assert result.name is None
        assert result.cars is None
        assert result.temp_access_token is None

    def test_complete_app_login_result_returns_user_and_cars(
        self,
        get_login_session_status_service,
        fake_app_login_result_store,
        fake_qr_session_store,
    ):
        """app_login_result가 있으면 complete와 차량 목록을 반환한다."""
        fake_app_login_result_store.add_complete_result(VALID_SESSION_ID)
        command = GetLoginSessionStatusCommand(session_id=VALID_SESSION_ID)

        result = get_login_session_status_service.execute(command)

        assert result.status == "complete"
        assert result.user_id == VALID_USER_ID
        assert result.name == VALID_USER_NAME
        assert result.cars == VALID_CARS
        assert result.temp_access_token == VALID_TEMP_ACCESS_TOKEN
        assert fake_qr_session_store.get_session_calls == []

    def test_missing_session_raises_error(
        self,
        get_login_session_status_service,
    ):
        """세션이 없으면 실패한다."""
        command = GetLoginSessionStatusCommand(session_id=INVALID_SESSION_ID)

        with pytest.raises(ValueError) as exc_info:
            get_login_session_status_service.execute(command)

        assert str(exc_info.value) == ERROR_SESSION_NOT_FOUND

    def test_empty_session_id_raises_error(
        self,
        get_login_session_status_service,
        fake_app_login_result_store,
        fake_qr_session_store,
    ):
        """session_id가 비어 있으면 실패한다."""
        command = GetLoginSessionStatusCommand(session_id="")

        with pytest.raises(ValueError) as exc_info:
            get_login_session_status_service.execute(command)

        assert str(exc_info.value) == ERROR_SESSION_ID_REQUIRED
        assert fake_app_login_result_store.get_result_calls == []
        assert fake_qr_session_store.get_session_calls == []

    def test_expired_qr_session_raises_error(
        self,
        get_login_session_status_service,
        fake_qr_session_store,
    ):
        """QR 세션이 만료 상태이면 실패한다."""
        fake_qr_session_store.add_session(
            session_id=EXPIRED_SESSION_ID,
            status="expired",
        )
        command = GetLoginSessionStatusCommand(session_id=EXPIRED_SESSION_ID)

        with pytest.raises(ValueError) as exc_info:
            get_login_session_status_service.execute(command)

        assert str(exc_info.value) == ERROR_SESSION_EXPIRED

    def test_failed_oauth_session_raises_error(
        self,
        get_login_session_status_service,
        fake_qr_session_store,
    ):
        """OAuth 실패 상태이면 실패한다."""
        fake_qr_session_store.add_session(
            session_id=FAILED_SESSION_ID,
            status="failed",
        )
        command = GetLoginSessionStatusCommand(session_id=FAILED_SESSION_ID)

        with pytest.raises(ValueError) as exc_info:
            get_login_session_status_service.execute(command)

        assert str(exc_info.value) == ERROR_OAUTH_FAILED

    def test_failed_app_login_result_raises_error(
        self,
        get_login_session_status_service,
        fake_app_login_result_store,
        fake_qr_session_store,
    ):
        """app_login_result가 failed이면 QR 세션 조회 없이 실패한다."""
        fake_app_login_result_store.add_failed_result(FAILED_SESSION_ID)
        command = GetLoginSessionStatusCommand(session_id=FAILED_SESSION_ID)

        with pytest.raises(ValueError) as exc_info:
            get_login_session_status_service.execute(command)

        assert str(exc_info.value) == ERROR_OAUTH_FAILED
        assert fake_qr_session_store.get_session_calls == []
