"""
QR 로그인 / 현대 OAuth 유스케이스 단위 테스트
UC-AUTH-001: QR 로그인 세션 생성
"""

import pytest

from app.application.auth.create_qr_session import (
    CreateQrSessionCommand,
    CreateQrSessionService,
)


VALID_SESSION_ID = "sess-001"
VALID_VIN_HASH = "vin-hash-001"
PUBLIC_BASE_URL = "https://api.carpayin.test"


class FakeQrSessionStore:
    def __init__(self):
        self.saved_sessions = {}

    def save_pending_session(self, *, session_id: str, vin_hash: str, ttl_seconds: int):
        self.saved_sessions[session_id] = {
            "session_id": session_id,
            "vin_hash": vin_hash,
            "status": "pending",
            "ttl_seconds": ttl_seconds,
        }


@pytest.fixture
def fake_qr_session_store():
    return FakeQrSessionStore()


@pytest.fixture
def create_qr_session_service(fake_qr_session_store):
    return CreateQrSessionService(
        qr_session_store=fake_qr_session_store,
        public_base_url=PUBLIC_BASE_URL,
    )


class TestCreateQrSession:
    """UC-AUTH-001 - POST /auth/qr-session"""

    def test_valid_request_stores_pending_session(
        self,
        create_qr_session_service,
        fake_qr_session_store,
    ):
        """유효한 요청이면 QR 세션을 pending 상태로 저장한다."""
        command = CreateQrSessionCommand(
            login_session_id=VALID_SESSION_ID,
            vin_hash=VALID_VIN_HASH,
        )

        create_qr_session_service.execute(command)

        saved = fake_qr_session_store.saved_sessions[VALID_SESSION_ID]
        assert saved["session_id"] == VALID_SESSION_ID
        assert saved["vin_hash"] == VALID_VIN_HASH
        assert saved["status"] == "pending"
        assert saved["ttl_seconds"] == 15 * 60

    def test_valid_request_returns_backend_login_url(self, create_qr_session_service):
        """유효한 요청이면 QR에 표시할 백엔드 로그인 URL을 반환한다."""
        command = CreateQrSessionCommand(
            login_session_id=VALID_SESSION_ID,
            vin_hash=VALID_VIN_HASH,
        )

        result = create_qr_session_service.execute(command)

        assert result.login_url == (
            f"{PUBLIC_BASE_URL}/auth/hyundai/start"
            f"?session_id={VALID_SESSION_ID}"
        )

    def test_empty_session_id_raises_error(self, create_qr_session_service):
        """session_id가 비어 있으면 실패한다."""
        command = CreateQrSessionCommand(
            login_session_id="",
            vin_hash=VALID_VIN_HASH,
        )

        with pytest.raises(ValueError) as exc_info:
            create_qr_session_service.execute(command)

        assert str(exc_info.value) == "login_session_id is required"

    def test_empty_vin_hash_raises_error(self, create_qr_session_service):
        """vin_hash가 비어 있으면 실패한다."""
        command = CreateQrSessionCommand(
            login_session_id=VALID_SESSION_ID,
            vin_hash="",
        )

        with pytest.raises(ValueError) as exc_info:
            create_qr_session_service.execute(command)

        assert str(exc_info.value) == "vin_hash is required"
