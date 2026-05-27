from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.card.approve_card_payment import ApproveCardPaymentService
from app.application.card.verify_and_tokenize_card import VerifyAndTokenizeCardService
from app.infra.db.session import get_db_session
from app.infra.repositories.card_repository import SqlAlchemyCardRepository
from app.infra.repositories.card_transaction_repository import (
    SqlAlchemyCardTransactionRepository,
)


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


def get_approve_card_payment_service(
    session: Session = Depends(get_db_session),
) -> ApproveCardPaymentService:
    return ApproveCardPaymentService(
        card_token_repository=SqlAlchemyCardRepository(session),
        card_transaction_repository=SqlAlchemyCardTransactionRepository(session),
    )
