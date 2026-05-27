from dataclasses import dataclass


HYUNDAI_ACCESS_TOKEN_TTL_SECONDS = 60 * 60
HYUNDAI_OAUTH_RESULT_TTL_SECONDS = 15 * 60
APP_LOGIN_RESULT_TTL_SECONDS = 5 * 60


@dataclass(frozen=True)
class HandleHyundaiOAuthCallbackCommand:
    code: str
    state: str


@dataclass(frozen=True)
class HandleHyundaiOAuthCallbackResult:
    status: str
    session_id: str
    user_id: str
    name: str
    cars: list[dict]
    temp_access_token: str


class HandleHyundaiOAuthCallbackService:
    def __init__(
        self,
        oauth_state_store,
        qr_session_store,
        hyundai_oauth_client,
        user_repository,
        hyundai_token_repository,
        hyundai_access_token_store,
        hyundai_oauth_result_store,
        app_login_result_store,
        temp_access_token_issuer,
        refresh_token_encryptor,
        public_base_url: str,
    ):
        self.oauth_state_store = oauth_state_store
        self.qr_session_store = qr_session_store
        self.hyundai_oauth_client = hyundai_oauth_client
        self.user_repository = user_repository
        self.hyundai_token_repository = hyundai_token_repository
        self.hyundai_access_token_store = hyundai_access_token_store
        self.hyundai_oauth_result_store = hyundai_oauth_result_store
        self.app_login_result_store = app_login_result_store
        self.temp_access_token_issuer = temp_access_token_issuer
        self.refresh_token_encryptor = refresh_token_encryptor
        self.public_base_url = public_base_url.rstrip("/")

    def execute(
        self,
        command: HandleHyundaiOAuthCallbackCommand,
    ) -> HandleHyundaiOAuthCallbackResult:
        if not command.code:
            raise ValueError("code is required")

        if not command.state:
            raise ValueError("state is required")

        session_id = self.oauth_state_store.get_session_id(command.state)
        if not session_id:
            raise ValueError("oauth_state_not_found")

        qr_session = self.qr_session_store.get_session(session_id)
        if not qr_session:
            raise ValueError("qr_session_not_found")

        if qr_session.get("status") == "expired":
            raise ValueError("qr_session_expired")

        try:
            token_data = self.hyundai_oauth_client.exchange_code(
                code=command.code,
                redirect_uri=f"{self.public_base_url}/auth/redirect",
            )
            access_token = token_data["access_token"]
            refresh_token = token_data["refresh_token"]

            profile = self.hyundai_oauth_client.get_user_profile(
                access_token=access_token,
            )
            user_id = profile["user_id"]
            name = profile["name"]

            cars = self.hyundai_oauth_client.get_vehicle_list(
                access_token=access_token,
            )
        except Exception as exc:
            self.qr_session_store.mark_failed(
                session_id=session_id,
                reason=str(exc),
            )
            raise

        encrypted_refresh_token = self.refresh_token_encryptor.encrypt(refresh_token)
        temp_access_token = self.temp_access_token_issuer.issue(
            user_id=user_id,
            session_id=session_id,
        )

        self.user_repository.upsert_user(user_id=user_id, name=name)
        self.hyundai_token_repository.upsert_token(
            user_id=user_id,
            encrypted_refresh_token=encrypted_refresh_token,
        )
        self.hyundai_access_token_store.save_access_token(
            user_id=user_id,
            access_token=access_token,
            ttl_seconds=HYUNDAI_ACCESS_TOKEN_TTL_SECONDS,
        )
        self.hyundai_oauth_result_store.save_result(
            session_id=session_id,
            user_id=user_id,
            name=name,
            cars=cars,
            temp_access_token=temp_access_token,
            ttl_seconds=HYUNDAI_OAUTH_RESULT_TTL_SECONDS,
        )
        self.app_login_result_store.save_result(
            session_id=session_id,
            status="complete",
            user_id=user_id,
            name=name,
            cars=cars,
            temp_access_token=temp_access_token,
            ttl_seconds=APP_LOGIN_RESULT_TTL_SECONDS,
        )
        self.oauth_state_store.mark_used(command.state)

        return HandleHyundaiOAuthCallbackResult(
            status="complete",
            session_id=session_id,
            user_id=user_id,
            name=name,
            cars=cars,
            temp_access_token=temp_access_token,
        )
