import os

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.pg.charge_billing_key import ChargeBillingKeyService
from app.application.pg.complete_card_registration import (
    CompleteCardRegistrationService,
)
from app.infra.clients import HttpxCarPayInWebhookClient, HttpxMockCardClient
from app.infra.db.session import get_db_session
from app.infra.repositories.billing_key_repository import (
    SqlAlchemyBillingKeyRepository,
)
from app.infra.repositories.transaction_repository import (
    SqlAlchemyTransactionRepository,
)


def _requires_explicit_env() -> bool:
    return os.getenv("APP_ENV", "local").strip().lower() in {
        "aws",
        "staging",
        "prod",
        "production",
    }


def _env_or_default(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    if _requires_explicit_env():
        raise RuntimeError(f"{name} environment variable is required")
    return default


mock_card_client = HttpxMockCardClient(
    base_url=_env_or_default("MOCK_CARD_BASE_URL", "http://localhost:8003"),
)
carpayin_webhook_client = HttpxCarPayInWebhookClient(
    base_url=_env_or_default("CARPAYIN_BACKEND_BASE_URL", "http://localhost:8000"),
    webhook_secret=_env_or_default("PG_WEBHOOK_SECRET", "mock-pg-webhook-secret"),
)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_complete_card_registration_service(
    session: Session = Depends(get_db_session),
) -> CompleteCardRegistrationService:
    return CompleteCardRegistrationService(
        mock_card_client=mock_card_client,
        billing_key_repository=SqlAlchemyBillingKeyRepository(session),
        carpayin_webhook_client=carpayin_webhook_client,
        allow_local_fallback=_env_bool(
            "MOCK_PG_ALLOW_FAKE_CARD_ON_VERIFY_FAILURE",
            False,
        ),
    )


def get_charge_billing_key_service(
    session: Session = Depends(get_db_session),
) -> ChargeBillingKeyService:
    return ChargeBillingKeyService(
        billing_key_repository=SqlAlchemyBillingKeyRepository(session),
        transaction_repository=SqlAlchemyTransactionRepository(session),
        mock_card_client=mock_card_client,
    )
