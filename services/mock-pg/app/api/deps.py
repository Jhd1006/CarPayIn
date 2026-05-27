from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.pg.charge_billing_key import ChargeBillingKeyService
from app.application.pg.complete_card_registration import (
    CompleteCardRegistrationService,
)
from app.infra.db.session import get_db_session
from app.infra.repositories.billing_key_repository import (
    SqlAlchemyBillingKeyRepository,
)
from app.infra.repositories.transaction_repository import (
    SqlAlchemyTransactionRepository,
)


class NotConfiguredDependency:
    def __getattr__(self, name):
        raise RuntimeError("dependency_not_configured")


def get_complete_card_registration_service(
    session: Session = Depends(get_db_session),
) -> CompleteCardRegistrationService:
    placeholder = NotConfiguredDependency()
    return CompleteCardRegistrationService(
        mock_card_client=placeholder,
        billing_key_repository=SqlAlchemyBillingKeyRepository(session),
        carpayin_webhook_client=placeholder,
    )


def get_charge_billing_key_service(
    session: Session = Depends(get_db_session),
) -> ChargeBillingKeyService:
    placeholder = NotConfiguredDependency()
    return ChargeBillingKeyService(
        billing_key_repository=SqlAlchemyBillingKeyRepository(session),
        transaction_repository=SqlAlchemyTransactionRepository(session),
        mock_card_client=placeholder,
    )
