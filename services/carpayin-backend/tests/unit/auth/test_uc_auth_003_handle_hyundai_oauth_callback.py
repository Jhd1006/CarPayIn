"""
QR 로그인 / 현대 OAuth 유스케이스 단위 테스트
UC-AUTH-003: 현대 OAuth callback 처리
"""

import pytest

from app.application.auth.handle_hyundai_oauth_callback import (
    APP_LOGIN_RESULT_TTL_SECONDS,
    HandleHyundaiOAuthCallbackCommand,
    HandleHyundaiOAuthCallbackService,
)


VALID_CODE = "hyundai-code-001"
VALID_OAUTH_STATE = "oauth-state-001"
VALID_SESSION_ID = "sess-001"
VALID_USER_ID = "hyundai-user-001"
VALID_USER_NAME = "홍길동"
VALID_HYUNDAI_ACCESS_TOKEN = "hyundai-access-001"
VALID_HYUNDAI_REFRESH_TOKEN = "hyundai-refresh-001"
VALID_TEMP_ACCESS_TOKEN = "temp-access-001"
VALID_REDIRECT_URI = "https://api.carpayin.test/auth/redirect"
PUBLIC_BASE_URL = "https://api.carpayin.test"
INVALID_OAUTH_STATE = "oauth-state-missing"
ERROR_CODE_REQUIRED = "code is required"
ERROR_OAUTH_STATE_NOT_FOUND = "oauth_state_not_found"
HYUNDAI_TOKEN_API_ERROR = "hyundai token api failed"
VALID_CARS = [
    {
        "car_id": "hyundai-car-001",
        "vin": "KMH001",
        "model": "IONIQ 5",
    },
    {
        "car_id": "hyundai-car-002",
        "vin": "KMH002",
        "model": "Sonata",
    },
]


class FakeOAuthStateStore:
    def __init__(self):
        self.states = {}
        self.used_states = []

    def add_state(self, *, oauth_state: str, session_id: str):
        self.states[oauth_state] = session_id

    def get_session_id(self, oauth_state: str):
        return self.states.get(oauth_state)

    def mark_used(self, oauth_state: str):
        self.used_states.append(oauth_state)


class FakeQrSessionStore:
    def __init__(self):
        self.sessions = {}
        self.failed_sessions = {}

    def add_pending_session(self, session_id: str):
        self.sessions[session_id] = {
            "session_id": session_id,
            "status": "pending",
        }

    def get_session(self, session_id: str):
        return self.sessions.get(session_id)

    def mark_failed(self, *, session_id: str, reason: str):
        self.failed_sessions[session_id] = {
            "session_id": session_id,
            "status": "failed",
            "reason": reason,
        }


class FakeHyundaiOAuthClient:
    def __init__(self):
        self.exchange_code_calls = []
        self.profile_calls = []
        self.vehicle_list_calls = []
        self.should_fail_exchange_code = False

    def exchange_code(self, *, code: str, redirect_uri: str):
        self.exchange_code_calls.append(
            {
                "code": code,
                "redirect_uri": redirect_uri,
            }
        )
        if self.should_fail_exchange_code:
            raise RuntimeError(HYUNDAI_TOKEN_API_ERROR)
        return {
            "access_token": VALID_HYUNDAI_ACCESS_TOKEN,
            "refresh_token": VALID_HYUNDAI_REFRESH_TOKEN,
        }

    def get_user_profile(self, *, access_token: str):
        self.profile_calls.append({"access_token": access_token})
        return {
            "user_id": VALID_USER_ID,
            "name": VALID_USER_NAME,
        }

    def get_vehicle_list(self, *, access_token: str):
        self.vehicle_list_calls.append({"access_token": access_token})
        return VALID_CARS


class FakeUserRepository:
    def __init__(self):
        self.users = {}

    def upsert_user(self, *, user_id: str, name: str):
        self.users[user_id] = {
            "user_id": user_id,
            "name": name,
        }


class FakeHyundaiOAuthResultStore:
    def __init__(self):
        self.results = {}

    def save_result(
        self,
        *,
        session_id: str,
        user_id: str,
        name: str,
        cars: list[dict],
        temp_access_token: str,
        ttl_seconds: int,
    ):
        self.results[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "name": name,
            "cars": cars,
            "temp_access_token": temp_access_token,
            "ttl_seconds": ttl_seconds,
        }


class FakeAppLoginResultStore:
    def __init__(self):
        self.results = {}

    def save_result(
        self,
        *,
        session_id: str,
        status: str,
        user_id: str,
        name: str,
        cars: list[dict],
        temp_access_token: str,
        ttl_seconds: int,
    ):
        self.results[session_id] = {
            "session_id": session_id,
            "status": status,
            "user_id": user_id,
            "name": name,
            "cars": cars,
            "temp_access_token": temp_access_token,
            "ttl_seconds": ttl_seconds,
        }


class FakeTempAccessTokenIssuer:
    def __init__(self):
        self.issue_calls = []

    def issue(self, *, user_id: str, session_id: str) -> str:
        self.issue_calls.append(
            {
                "user_id": user_id,
                "session_id": session_id,
            }
        )
        return VALID_TEMP_ACCESS_TOKEN


@pytest.fixture
def fake_oauth_state_store():
    return FakeOAuthStateStore()


@pytest.fixture
def fake_qr_session_store():
    return FakeQrSessionStore()


@pytest.fixture
def fake_hyundai_oauth_client():
    return FakeHyundaiOAuthClient()


@pytest.fixture
def fake_user_repository():
    return FakeUserRepository()


@pytest.fixture
def fake_hyundai_oauth_result_store():
    return FakeHyundaiOAuthResultStore()


@pytest.fixture
def fake_app_login_result_store():
    return FakeAppLoginResultStore()


@pytest.fixture
def fake_temp_access_token_issuer():
    return FakeTempAccessTokenIssuer()


@pytest.fixture
def handle_hyundai_oauth_callback_service(
    fake_oauth_state_store,
    fake_qr_session_store,
    fake_hyundai_oauth_client,
    fake_user_repository,
    fake_hyundai_oauth_result_store,
    fake_app_login_result_store,
    fake_temp_access_token_issuer,
):
    return HandleHyundaiOAuthCallbackService(
        oauth_state_store=fake_oauth_state_store,
        qr_session_store=fake_qr_session_store,
        hyundai_oauth_client=fake_hyundai_oauth_client,
        user_repository=fake_user_repository,
        hyundai_oauth_result_store=fake_hyundai_oauth_result_store,
        app_login_result_store=fake_app_login_result_store,
        temp_access_token_issuer=fake_temp_access_token_issuer,
        public_base_url=PUBLIC_BASE_URL,
    )


@pytest.fixture
def valid_oauth_state(
    fake_oauth_state_store,
    fake_qr_session_store,
):
    fake_oauth_state_store.add_state(
        oauth_state=VALID_OAUTH_STATE,
        session_id=VALID_SESSION_ID,
    )
    fake_qr_session_store.add_pending_session(VALID_SESSION_ID)


class TestHandleHyundaiOAuthCallback:
    """UC-AUTH-003 - GET /auth/redirect"""

    def test_valid_callback_stores_user_and_returns_complete(
        self,
        handle_hyundai_oauth_callback_service,
        fake_user_repository,
        valid_oauth_state,
    ):
        """정상 callback이면 user를 저장하고 complete 결과를 반환한다."""
        command = HandleHyundaiOAuthCallbackCommand(
            code=VALID_CODE,
            state=VALID_OAUTH_STATE,
        )

        result = handle_hyundai_oauth_callback_service.execute(command)

        assert result.status == "complete"
        assert fake_user_repository.users[VALID_USER_ID]["name"] == VALID_USER_NAME

    def test_valid_callback_stores_vehicle_list_in_app_login_result(
        self,
        handle_hyundai_oauth_callback_service,
        fake_app_login_result_store,
        fake_hyundai_oauth_result_store,
        fake_oauth_state_store,
        valid_oauth_state,
    ):
        """차량 목록과 차량 확정용 임시 token을 app_login_result에 저장한다."""
        command = HandleHyundaiOAuthCallbackCommand(
            code=VALID_CODE,
            state=VALID_OAUTH_STATE,
        )

        result = handle_hyundai_oauth_callback_service.execute(command)

        saved = fake_app_login_result_store.results[VALID_SESSION_ID]
        assert saved["status"] == "complete"
        assert saved["cars"] == VALID_CARS
        assert saved["temp_access_token"] == VALID_TEMP_ACCESS_TOKEN
        assert saved["ttl_seconds"] == APP_LOGIN_RESULT_TTL_SECONDS
        assert result.cars == VALID_CARS
        assert result.temp_access_token == VALID_TEMP_ACCESS_TOKEN
        assert fake_hyundai_oauth_result_store.results[VALID_SESSION_ID]["cars"] == (
            VALID_CARS
        )
        assert fake_oauth_state_store.used_states == [VALID_OAUTH_STATE]

    def test_invalid_state_raises_error_without_external_calls(
        self,
        handle_hyundai_oauth_callback_service,
        fake_hyundai_oauth_client,
    ):
        """잘못된 state이면 현대 API를 호출하지 않고 실패한다."""
        command = HandleHyundaiOAuthCallbackCommand(
            code=VALID_CODE,
            state=INVALID_OAUTH_STATE,
        )

        with pytest.raises(ValueError) as exc_info:
            handle_hyundai_oauth_callback_service.execute(command)

        assert str(exc_info.value) == ERROR_OAUTH_STATE_NOT_FOUND
        assert fake_hyundai_oauth_client.exchange_code_calls == []
        assert fake_hyundai_oauth_client.profile_calls == []
        assert fake_hyundai_oauth_client.vehicle_list_calls == []

    def test_empty_code_raises_error(
        self,
        handle_hyundai_oauth_callback_service,
    ):
        """code가 비어 있으면 실패한다."""
        command = HandleHyundaiOAuthCallbackCommand(
            code="",
            state=VALID_OAUTH_STATE,
        )

        with pytest.raises(ValueError) as exc_info:
            handle_hyundai_oauth_callback_service.execute(command)

        assert str(exc_info.value) == ERROR_CODE_REQUIRED

    def test_hyundai_api_failure_marks_qr_session_failed(
        self,
        handle_hyundai_oauth_callback_service,
        fake_hyundai_oauth_client,
        fake_qr_session_store,
        valid_oauth_state,
    ):
        """현대 API가 실패하면 QR 세션을 failed로 표시한다."""
        fake_hyundai_oauth_client.should_fail_exchange_code = True
        command = HandleHyundaiOAuthCallbackCommand(
            code=VALID_CODE,
            state=VALID_OAUTH_STATE,
        )

        with pytest.raises(RuntimeError) as exc_info:
            handle_hyundai_oauth_callback_service.execute(command)

        assert str(exc_info.value) == HYUNDAI_TOKEN_API_ERROR
        failed = fake_qr_session_store.failed_sessions[VALID_SESSION_ID]
        assert failed["status"] == "failed"
        assert failed["reason"] == HYUNDAI_TOKEN_API_ERROR
