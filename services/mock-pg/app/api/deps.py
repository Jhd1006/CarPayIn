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


mock_card_client = HttpxMockCardClient(
    base_url=os.getenv("MOCK_CARD_BASE_URL", "http://localhost:8003"),
)
carpayin_webhook_client = HttpxCarPayInWebhookClient(
    base_url=os.getenv("CARPAYIN_BACKEND_BASE_URL", "http://localhost:8000"),
    webhook_secret=os.getenv("PG_WEBHOOK_SECRET", "mock-pg-webhook-secret"),
)


def get_complete_card_registration_service(
    session: Session = Depends(get_db_session),
) -> CompleteCardRegistrationService:
    return CompleteCardRegistrationService(
        mock_card_client=mock_card_client,
        billing_key_repository=SqlAlchemyBillingKeyRepository(session),
        carpayin_webhook_client=carpayin_webhook_client,
    )


def get_charge_billing_key_service(
    session: Session = Depends(get_db_session),
) -> ChargeBillingKeyService:
    return ChargeBillingKeyService(
        billing_key_repository=SqlAlchemyBillingKeyRepository(session),
        transaction_repository=SqlAlchemyTransactionRepository(session),
        mock_card_client=mock_card_client,
    )
