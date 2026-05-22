from app.application.card.approve_card_payment import ApproveCardPaymentService
from app.application.card.verify_and_tokenize_card import VerifyAndTokenizeCardService


class NotConfiguredDependency:
    def __getattr__(self, name):
        raise RuntimeError("dependency_not_configured")


def get_verify_and_tokenize_card_service() -> VerifyAndTokenizeCardService:
    placeholder = NotConfiguredDependency()
    return VerifyAndTokenizeCardService(
        card_validator=placeholder,
        card_token_repository=placeholder,
        card_encryptor=placeholder,
    )


def get_approve_card_payment_service() -> ApproveCardPaymentService:
    placeholder = NotConfiguredDependency()
    return ApproveCardPaymentService(
        card_token_repository=placeholder,
        card_transaction_repository=placeholder,
    )
