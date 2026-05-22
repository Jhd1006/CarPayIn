from app.application.auth.confirm_vehicle import ConfirmVehicleService
from app.application.auth.create_qr_session import CreateQrSessionService
from app.application.auth.get_login_session_status import GetLoginSessionStatusService
from app.application.auth.handle_hyundai_oauth_callback import (
    HandleHyundaiOAuthCallbackService,
)
from app.application.auth.refresh_access_token import RefreshAccessTokenService
from app.application.auth.start_hyundai_oauth import StartHyundaiOAuthService
from app.application.parking.handle_entry_webhook import HandleEntryWebhookService
from app.application.parking.register_pre_notify import RegisterPreNotifyService


PUBLIC_BASE_URL = "https://api.carpayin.test"
HYUNDAI_AUTHORIZE_URL = "https://accounts.hyundai.test/oauth2/authorize"
HYUNDAI_CLIENT_ID = "hyundai-client-001"


class InMemoryQrSessionStore:
    def __init__(self):
        self.sessions = {}

    def save_pending_session(self, *, session_id: str, vin_hash: str, ttl_seconds: int):
        self.sessions[session_id] = {
            "session_id": session_id,
            "vin_hash": vin_hash,
            "status": "pending",
            "ttl_seconds": ttl_seconds,
        }

    def get_session(self, session_id: str):
        return self.sessions.get(session_id)

    def mark_failed(self, *, session_id: str, reason: str):
        session = self.sessions.setdefault(session_id, {"session_id": session_id})
        session["status"] = "failed"
        session["reason"] = reason


class InMemoryOAuthStateStore:
    def __init__(self):
        self.states = {}
        self.used_states = set()

    def save_oauth_state(self, *, oauth_state: str, session_id: str, ttl_seconds: int):
        self.states[oauth_state] = {
            "session_id": session_id,
            "ttl_seconds": ttl_seconds,
        }

    def get_session_id(self, oauth_state: str):
        state = self.states.get(oauth_state)
        if not state or oauth_state in self.used_states:
            return None
        return state["session_id"]

    def mark_used(self, oauth_state: str):
        self.used_states.add(oauth_state)


class InMemoryAppLoginResultStore:
    def __init__(self):
        self.results = {}

    def get_result(self, session_id: str):
        return self.results.get(session_id)

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
            "status": status,
            "user_id": user_id,
            "name": name,
            "cars": cars,
            "temp_access_token": temp_access_token,
            "ttl_seconds": ttl_seconds,
        }


class NotConfiguredDependency:
    def __getattr__(self, name):
        raise RuntimeError("dependency_not_configured")


qr_session_store = InMemoryQrSessionStore()
oauth_state_store = InMemoryOAuthStateStore()
app_login_result_store = InMemoryAppLoginResultStore()


def get_create_qr_session_service() -> CreateQrSessionService:
    return CreateQrSessionService(
        qr_session_store=qr_session_store,
        public_base_url=PUBLIC_BASE_URL,
    )


def get_start_hyundai_oauth_service() -> StartHyundaiOAuthService:
    return StartHyundaiOAuthService(
        qr_session_store=qr_session_store,
        oauth_state_store=oauth_state_store,
        public_base_url=PUBLIC_BASE_URL,
        hyundai_authorize_url=HYUNDAI_AUTHORIZE_URL,
        hyundai_client_id=HYUNDAI_CLIENT_ID,
    )


def get_handle_hyundai_oauth_callback_service() -> HandleHyundaiOAuthCallbackService:
    placeholder = NotConfiguredDependency()
    return HandleHyundaiOAuthCallbackService(
        oauth_state_store=oauth_state_store,
        qr_session_store=qr_session_store,
        hyundai_oauth_client=placeholder,
        user_repository=placeholder,
        hyundai_token_repository=placeholder,
        hyundai_access_token_store=placeholder,
        hyundai_oauth_result_store=placeholder,
        app_login_result_store=app_login_result_store,
        temp_access_token_issuer=placeholder,
        refresh_token_encryptor=placeholder,
        public_base_url=PUBLIC_BASE_URL,
    )


def get_login_session_status_service() -> GetLoginSessionStatusService:
    return GetLoginSessionStatusService(
        app_login_result_store=app_login_result_store,
        qr_session_store=qr_session_store,
    )


def get_confirm_vehicle_service() -> ConfirmVehicleService:
    placeholder = NotConfiguredDependency()
    return ConfirmVehicleService(
        temp_access_token_validator=placeholder,
        hyundai_oauth_result_store=placeholder,
        app_login_result_store=app_login_result_store,
        qr_session_store=qr_session_store,
        vehicle_repository=placeholder,
        app_refresh_token_repository=placeholder,
        app_token_issuer=placeholder,
        refresh_token_hasher=placeholder,
    )


def get_refresh_access_token_service() -> RefreshAccessTokenService:
    placeholder = NotConfiguredDependency()
    return RefreshAccessTokenService(
        app_refresh_token_repository=placeholder,
        refresh_token_hasher=placeholder,
        app_access_token_issuer=placeholder,
    )


def get_register_pre_notify_service() -> RegisterPreNotifyService:
    placeholder = NotConfiguredDependency()
    return RegisterPreNotifyService(
        token_validator=placeholder,
        vehicle_repository=placeholder,
        billing_key_repository=placeholder,
        pre_notify_store=placeholder,
        pms_client=placeholder,
        plate_normalizer=placeholder,
    )


def get_handle_entry_webhook_service() -> HandleEntryWebhookService:
    placeholder = NotConfiguredDependency()
    return HandleEntryWebhookService(
        pms_auth_validator=placeholder,
        pre_notify_store=placeholder,
        parking_session_repository=placeholder,
        notification_publisher=placeholder,
    )
