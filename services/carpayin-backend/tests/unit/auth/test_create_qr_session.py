from app.application.auth.create_qr_session import (
    CreateQrSessionCommand,
    CreateQrSessionService,
)

# Redis 대체 가짜 저장소 : Python dict 저장
class FakeQrSessionStore:
    def __init__(self):
        self.saved_sessions = {}

    def save_pending_session(self, session_id, vin_hash, ttl_seconds):
        self.saved_sessions[session_id] = {
            "session_id": session_id,
            "vin_hash": vin_hash,
            "status": "pending",
            "ttl_seconds": ttl_seconds,
        }


# QR 세션을 생성하면 pending 세션으로 저장되어야 한다
def test_create_qr_session_saves_pending_session():
    # given
    store = FakeQrSessionStore()
    service = CreateQrSessionService(
        qr_session_store=store,
        public_base_url="https://api.carpayin.test",
    )

    command = CreateQrSessionCommand(
        login_session_id="sess_123",
        vin_hash="hash_abc",
    )

    # when
    service.execute(command)

    # then
    saved = store.saved_sessions["sess_123"]

    assert saved["session_id"] == "sess_123"
    assert saved["vin_hash"] == "hash_abc"
    assert saved["status"] == "pending"
    assert saved["ttl_seconds"] == 15 * 60


# QR 세션을 만들면 앱에 login_url을 돌려줘야 한다
def test_create_qr_session_returns_backend_login_url():
    # given
    store = FakeQrSessionStore()
    service = CreateQrSessionService(
        qr_session_store=store,
        public_base_url="https://api.carpayin.test",
    )

    command = CreateQrSessionCommand(
        login_session_id="sess_123",
        vin_hash="hash_abc",
    )

    # when
    result = service.execute(command)

    # then
    assert result.login_url == (
        "https://api.carpayin.test/auth/hyundai/start"
        "?session_id=sess_123"
    )


# session_id가 비어 있으면 실패해야 한다
def test_create_qr_session_rejects_empty_session_id():
    # given
    store = FakeQrSessionStore()
    service = CreateQrSessionService(
        qr_session_store=store,
        public_base_url="https://api.carpayin.test",
    )

    command = CreateQrSessionCommand(
        login_session_id="",
        vin_hash="hash_abc",
    )

    # when / then
    try:
        service.execute(command)
        assert False, "Expected ValueError"
    except ValueError as error:
        assert str(error) == "login_session_id is required"


# vin_hash가 비어 있으면 실패해야 한다
def test_create_qr_session_rejects_empty_vin_hash():
    # given
    store = FakeQrSessionStore()
    service = CreateQrSessionService(
        qr_session_store=store,
        public_base_url="https://api.carpayin.test",
    )

    command = CreateQrSessionCommand(
        login_session_id="sess_123",
        vin_hash="",
    )

    # when / then
    try:
        service.execute(command)
        assert False, "Expected ValueError"
    except ValueError as error:
        assert str(error) == "vin_hash is required"
