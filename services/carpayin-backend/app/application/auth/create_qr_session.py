from dataclasses import dataclass


QR_SESSION_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class CreateQrSessionCommand:
    login_session_id: str
    vin_hash: str


@dataclass(frozen=True)
class CreateQrSessionResult:
    login_url: str


class CreateQrSessionService:
    def __init__(self, qr_session_store, public_base_url: str):
        self.qr_session_store = qr_session_store
        self.public_base_url = public_base_url.rstrip("/")

    def execute(self, command: CreateQrSessionCommand) -> CreateQrSessionResult:
        if not command.login_session_id:
            raise ValueError("login_session_id is required")

        if not command.vin_hash:
            raise ValueError("vin_hash is required")

        self.qr_session_store.save_pending_session(
            session_id=command.login_session_id,
            vin_hash=command.vin_hash,
            ttl_seconds=QR_SESSION_TTL_SECONDS,
        )

        login_url = (
            f"{self.public_base_url}/auth/hyundai/start"
            f"?session_id={command.login_session_id}"
        )

        return CreateQrSessionResult(login_url=login_url)
