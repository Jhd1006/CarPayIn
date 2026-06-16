import os

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.pms.calculate_fee import CalculateFeeService
from app.application.pms.handle_lpr_entry import HandleLprEntryService
from app.application.pms.handle_lpr_exit import HandleLprExitService
from app.application.pms.record_payment_complete import RecordPaymentCompleteService
from app.application.pms.register_pre_notify import RegisterPreNotifyService
from app.infra.clients import HttpxCarPayInWebhookClient
from app.infra.db.session import get_db_session
from app.infra.fees import SimpleFeeCalculator
from app.infra.mqtt import build_barrier_publisher
from app.infra.redis import RedisPreRegistrationStore, redis_client
from app.infra.repositories.payment_request_repository import SqlAlchemyPaymentRequestRepository
from app.infra.repositories.pms_session_repository import SqlAlchemyPmsSessionRepository
from app.infra.security import WebhookSignatureVerifier


def _requires_explicit_env():
    return os.getenv("APP_ENV", "local").strip().lower() in {"aws", "staging", "prod", "production"}


def _env_or_default(name, default):
    value = os.getenv(name, "").strip()
    if value:
        return value
    if _requires_explicit_env():
        raise RuntimeError(f"{name} environment variable is required")
    return default


def _env_or_legacy_default(name, legacy_name, default):
    value = os.getenv(name, "").strip()
    if value:
        return value
    legacy_value = os.getenv(legacy_name, "").strip()
    if legacy_value:
        return legacy_value
    if _requires_explicit_env():
        raise RuntimeError(f"{name} environment variable is required")
    return default


PMS_WEBHOOK_SECRET = _env_or_legacy_default(
    "PMS_WEBHOOK_SECRET",
    "PMS_WEBHOOK_TOKEN",
    "pms-webhook-secret",
)


carpayin_webhook_client = HttpxCarPayInWebhookClient(
    base_url=_env_or_default("CARPAYIN_BACKEND_BASE_URL", "http://localhost:8000"),
    webhook_token=PMS_WEBHOOK_SECRET,
)
payment_webhook_signature_verifier = WebhookSignatureVerifier(PMS_WEBHOOK_SECRET)
fee_calculator = SimpleFeeCalculator(
    amount_per_30_minutes=int(os.getenv("PMS_FEE_PER_30_MINUTES", "500")),
)
barrier_publisher = build_barrier_publisher()
pre_registration_store = RedisPreRegistrationStore(redis_client)


def get_register_pre_notify_service() -> RegisterPreNotifyService:
    return RegisterPreNotifyService(
        pre_registration_repository=pre_registration_store,
    )


def get_handle_lpr_entry_service(session: Session = Depends(get_db_session)) -> HandleLprEntryService:
    return HandleLprEntryService(
        pre_registration_repository=pre_registration_store,
        pms_session_repository=SqlAlchemyPmsSessionRepository(session),
        carpayin_webhook_client=carpayin_webhook_client,
        barrier_publisher=barrier_publisher,
    )


def get_calculate_fee_service(session: Session = Depends(get_db_session)) -> CalculateFeeService:
    return CalculateFeeService(
        pms_session_repository=SqlAlchemyPmsSessionRepository(session),
        fee_calculator=fee_calculator,
    )


def get_handle_lpr_exit_service(session: Session = Depends(get_db_session)) -> HandleLprExitService:
    return HandleLprExitService(
        pms_session_repository=SqlAlchemyPmsSessionRepository(session),
        barrier_publisher=barrier_publisher,
    )


def get_record_payment_complete_service(session: Session = Depends(get_db_session)) -> RecordPaymentCompleteService:
    return RecordPaymentCompleteService(
        payment_request_repository=SqlAlchemyPaymentRequestRepository(session),
        pms_session_repository=SqlAlchemyPmsSessionRepository(session),
        barrier_publisher=barrier_publisher,
    )


def get_payment_webhook_signature_verifier() -> WebhookSignatureVerifier:
    return payment_webhook_signature_verifier
