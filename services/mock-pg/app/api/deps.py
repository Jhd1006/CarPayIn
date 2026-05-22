from app.application.pg.charge_billing_key import ChargeBillingKeyService
from app.application.pg.complete_card_registration import (
    CompleteCardRegistrationService,
)


class NotConfiguredDependency:
    def __getattr__(self, name):
        raise RuntimeError("dependency_not_configured")


def get_complete_card_registration_service() -> CompleteCardRegistrationService:
    placeholder = NotConfiguredDependency()
    return CompleteCardRegistrationService(
        mock_card_client=placeholder,
        billing_key_repository=placeholder,
        carpayin_webhook_client=placeholder,
    )


def get_charge_billing_key_service() -> ChargeBillingKeyService:
    placeholder = NotConfiguredDependency()
    return ChargeBillingKeyService(
        billing_key_repository=placeholder,
        transaction_repository=placeholder,
        mock_card_client=placeholder,
    )
