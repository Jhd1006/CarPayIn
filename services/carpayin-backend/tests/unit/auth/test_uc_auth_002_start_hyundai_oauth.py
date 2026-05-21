"""
QR 로그인 / 현대 OAuth 유스케이스 단위 테스트
UC-AUTH-002: 현대 OAuth 로그인 시작
"""

from urllib.parse import parse_qs, urlparse

import pytest

from app.application.auth.start_hyundai_oauth import (
    OAUTH_STATE_TTL_SECONDS,
    StartHyundaiOAuthCommand,
    StartHyundaiOAuthService,
)


VALID_SESSION_ID = "sess-001"
VALID_VIN_HASH = "vin-hash-001"
VALID_OAUTH_STATE = "oauth-state-001"
EXPIRED_SESSION_ID = "sess-expired"
OTHER_SESSION_ID = "sess-complete"
INVALID_SESSION_ID = "sess-missing"
PUBLIC_BASE_URL = "https://api.carpayin.test"
EXPECTED_REDIRECT_URI = f"{PUBLIC_BASE_URL}/auth/redirect"
HYUNDAI_AUTHORIZE_URL = "https://accounts.hyundai.test/oauth2/authorize"
HYUNDAI_CLIENT_ID = "hyundai-client-001"
EXPECTED_RESPONSE_TYPE = "code"
EXPECTED_SCOPE = "openid profile"
ERROR_SESSION_ID_REQUIRED = "session_id is required"
ERROR_QR_SESSION_NOT_FOUND = "qr_session_not_found"
ERROR_QR_SESSION_EXPIRED = "qr_session_expired"
ERROR_QR_SESSION_NOT_PENDING = "qr_session_not_pending"


class FakeQrSessionStore:
    def __init__(self):
        self.sessions = {}

    def add_pending_session(self, session_id: str):
        self.add_session(session_id=session_id, status="pending")

    def add_session(self, *, session_id: str, status: str):
        self.sessions[session_id] = {
            "session_id": session_id,
            "vin_hash": VALID_VIN_HASH,
            "status": status,
        }

    def get_session(self, session_id: str):
        return self.sessions.get(session_id)


class FakeOAuthStateStore:
    def __init__(self):
        self.saved_states = {}

    def save_oauth_state(
        self,
        *,
        oauth_state: str,
        session_id: str,
        ttl_seconds: int,
    ):
        self.saved_states[oauth_state] = {
            "oauth_state": oauth_state,
            "session_id": session_id,
            "ttl_seconds": ttl_seconds,
        }


@pytest.fixture
def fake_qr_session_store():
    return FakeQrSessionStore()


@pytest.fixture
def fake_oauth_state_store():
    return FakeOAuthStateStore()


@pytest.fixture
def oauth_state_generator():
    return lambda: VALID_OAUTH_STATE


@pytest.fixture
def start_hyundai_oauth_service(
    fake_qr_session_store,
    fake_oauth_state_store,
    oauth_state_generator,
):
    return StartHyundaiOAuthService(
        qr_session_store=fake_qr_session_store,
        oauth_state_store=fake_oauth_state_store,
        public_base_url=PUBLIC_BASE_URL,
        hyundai_authorize_url=HYUNDAI_AUTHORIZE_URL,
        hyundai_client_id=HYUNDAI_CLIENT_ID,
        oauth_state_generator=oauth_state_generator,
    )


class TestStartHyundaiOAuth:
    """UC-AUTH-002 - GET /auth/hyundai/start?session_id={session_id}"""

    def test_pending_qr_session_stores_oauth_state(
        self,
        start_hyundai_oauth_service,
        fake_qr_session_store,
        fake_oauth_state_store,
    ):
        """pending QR 세션이면 oauth_state와 session_id 매핑을 저장한다."""
        fake_qr_session_store.add_pending_session(VALID_SESSION_ID)
        command = StartHyundaiOAuthCommand(session_id=VALID_SESSION_ID)

        start_hyundai_oauth_service.execute(command)

        saved = fake_oauth_state_store.saved_states[VALID_OAUTH_STATE]
        assert saved["oauth_state"] == VALID_OAUTH_STATE
        assert saved["session_id"] == VALID_SESSION_ID
        assert saved["ttl_seconds"] == OAUTH_STATE_TTL_SECONDS

    def test_pending_qr_session_returns_hyundai_redirect_url(
        self,
        start_hyundai_oauth_service,
        fake_qr_session_store,
    ):
        """pending QR 세션이면 현대 OAuth redirect URL을 반환한다."""
        fake_qr_session_store.add_pending_session(VALID_SESSION_ID)
        command = StartHyundaiOAuthCommand(session_id=VALID_SESSION_ID)

        result = start_hyundai_oauth_service.execute(command)

        parsed = urlparse(result.redirect_url)
        query = parse_qs(parsed.query)
        assert (
            f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            == HYUNDAI_AUTHORIZE_URL
        )
        assert query["client_id"] == [HYUNDAI_CLIENT_ID]
        assert query["redirect_uri"] == [EXPECTED_REDIRECT_URI]
        assert query["response_type"] == [EXPECTED_RESPONSE_TYPE]
        assert query["scope"] == [EXPECTED_SCOPE]
        assert query["state"] == [VALID_OAUTH_STATE]
        assert query["state"] != [VALID_SESSION_ID]

    def test_empty_session_id_raises_error(
        self,
        start_hyundai_oauth_service,
        fake_oauth_state_store,
    ):
        """session_id가 비어 있으면 실패한다."""
        command = StartHyundaiOAuthCommand(session_id="")

        with pytest.raises(ValueError) as exc_info:
            start_hyundai_oauth_service.execute(command)

        assert str(exc_info.value) == ERROR_SESSION_ID_REQUIRED
        assert fake_oauth_state_store.saved_states == {}

    def test_missing_qr_session_raises_error(
        self,
        start_hyundai_oauth_service,
        fake_oauth_state_store,
    ):
        """QR 세션이 없으면 실패한다."""
        command = StartHyundaiOAuthCommand(session_id=INVALID_SESSION_ID)

        with pytest.raises(ValueError) as exc_info:
            start_hyundai_oauth_service.execute(command)

        assert str(exc_info.value) == ERROR_QR_SESSION_NOT_FOUND
        assert fake_oauth_state_store.saved_states == {}

    def test_expired_qr_session_raises_error(
        self,
        start_hyundai_oauth_service,
        fake_qr_session_store,
        fake_oauth_state_store,
    ):
        """QR 세션이 만료 상태이면 실패한다."""
        fake_qr_session_store.add_session(
            session_id=EXPIRED_SESSION_ID,
            status="expired",
        )
        command = StartHyundaiOAuthCommand(session_id=EXPIRED_SESSION_ID)

        with pytest.raises(ValueError) as exc_info:
            start_hyundai_oauth_service.execute(command)

        assert str(exc_info.value) == ERROR_QR_SESSION_EXPIRED
        assert fake_oauth_state_store.saved_states == {}

    def test_non_pending_qr_session_raises_error(
        self,
        start_hyundai_oauth_service,
        fake_qr_session_store,
        fake_oauth_state_store,
    ):
        """QR 세션이 pending이 아니면 실패한다."""
        fake_qr_session_store.add_session(
            session_id=OTHER_SESSION_ID,
            status="complete",
        )
        command = StartHyundaiOAuthCommand(session_id=OTHER_SESSION_ID)

        with pytest.raises(ValueError) as exc_info:
            start_hyundai_oauth_service.execute(command)

        assert str(exc_info.value) == ERROR_QR_SESSION_NOT_PENDING
        assert fake_oauth_state_store.saved_states == {}
