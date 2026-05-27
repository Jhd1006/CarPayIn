from fastapi import Header, HTTPException

from app.application.auth.confirm_vehicle import ConfirmVehicleService
from app.application.auth.create_qr_session import CreateQrSessionService
from app.application.auth.get_login_session_status import GetLoginSessionStatusService
from app.application.auth.handle_hyundai_oauth_callback import (
    HandleHyundaiOAuthCallbackService,
)
from app.application.auth.refresh_access_token import RefreshAccessTokenService
from app.application.auth.start_hyundai_oauth import StartHyundaiOAuthService
from app.application.card.create_card_order import CreateCardOrderService
from app.application.card.handle_card_webhook import HandleCardWebhookService
from app.application.parking.handle_entry_webhook import HandleEntryWebhookService
from app.application.parking.register_pre_notify import RegisterPreNotifyService
from app.application.payment.get_parking_fee import GetParkingFeeService
from app.application.payment.process_payment import ProcessPaymentService
from app.infra.redis import (
    RedisAppLoginResultStore,
    RedisCardOrderStore,
    RedisFeeQuoteStore,
    RedisHyundaiAccessTokenStore,
    RedisHyundaiOAuthResultStore,
    RedisOAuthStateStore,
    RedisPreNotifyStore,
    RedisQrSessionStore,
    redis_client,
)


PUBLIC_BASE_URL = "https://api.carpayin.test"
HYUNDAI_AUTHORIZE_URL = "https://accounts.hyundai.test/oauth2/authorize"
HYUNDAI_CLIENT_ID = "hyundai-client-001"


class NotConfiguredDependency:
    def __getattr__(self, name):
        raise RuntimeError("dependency_not_configured")


qr_session_store = RedisQrSessionStore(redis_client)
oauth_state_store = RedisOAuthStateStore(redis_client)
hyundai_access_token_store = RedisHyundaiAccessTokenStore(redis_client)
hyundai_oauth_result_store = RedisHyundaiOAuthResultStore(redis_client)
app_login_result_store = RedisAppLoginResultStore(redis_client)
card_order_store = RedisCardOrderStore(redis_client)
pre_notify_store = RedisPreNotifyStore(redis_client)
fee_quote_store = RedisFeeQuoteStore(redis_client)


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "UNAUTHORIZED",
                "message": "missing_bearer_token",
            },
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "UNAUTHORIZED",
                "message": "missing_bearer_token",
            },
        )

    raise RuntimeError("dependency_not_configured")


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
        hyundai_access_token_store=hyundai_access_token_store,
        hyundai_oauth_result_store=hyundai_oauth_result_store,
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
        hyundai_oauth_result_store=hyundai_oauth_result_store,
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


def get_create_card_order_service() -> CreateCardOrderService:
    placeholder = NotConfiguredDependency()
    return CreateCardOrderService(
        vehicle_repository=placeholder,
        molit_client=placeholder,
        card_order_store=card_order_store,
        pg_client=placeholder,
        order_id_generator=placeholder,
    )


def get_handle_card_webhook_service() -> HandleCardWebhookService:
    placeholder = NotConfiguredDependency()
    return HandleCardWebhookService(
        card_order_store=card_order_store,
        billing_key_repository=placeholder,
        vehicle_repository=placeholder,
        signature_verifier=placeholder,
    )


def get_register_pre_notify_service() -> RegisterPreNotifyService:
    placeholder = NotConfiguredDependency()
    return RegisterPreNotifyService(
        token_validator=placeholder,
        vehicle_repository=placeholder,
        billing_key_repository=placeholder,
        pre_notify_store=pre_notify_store,
        pms_client=placeholder,
        plate_normalizer=placeholder,
    )


def get_handle_entry_webhook_service() -> HandleEntryWebhookService:
    placeholder = NotConfiguredDependency()
    return HandleEntryWebhookService(
        pms_auth_validator=placeholder,
        pre_notify_store=pre_notify_store,
        parking_session_repository=placeholder,
        notification_publisher=placeholder,
    )


def get_parking_fee_service() -> GetParkingFeeService:
    placeholder = NotConfiguredDependency()
    return GetParkingFeeService(
        token_validator=placeholder,
        parking_session_repository=placeholder,
        fee_quote_store=fee_quote_store,
        pms_client=placeholder,
    )


def get_process_payment_service() -> ProcessPaymentService:
    placeholder = NotConfiguredDependency()
    return ProcessPaymentService(
        token_validator=placeholder,
        fee_quote_store=fee_quote_store,
        parking_session_repository=placeholder,
        billing_key_repository=placeholder,
        transaction_repository=placeholder,
        pg_client=placeholder,
        pms_client=placeholder,
        notification_publisher=placeholder,
    )
