from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.card.approve_card_payment import ApproveCardPaymentService
from app.application.card.verify_and_tokenize_card import VerifyAndTokenizeCardService
from app.infra.db.session import get_db_session
from app.infra.repositories.card_repository import SqlAlchemyCardRepository
from app.infra.repositories.card_transaction_repository import (
    SqlAlchemyCardTransactionRepository,
)
from app.infra.security import MockCardEncryptor, MockCardValidator


def get_verify_and_tokenize_card_service(
    session: Session = Depends(get_db_session),
) -> VerifyAndTokenizeCardService:
    return VerifyAndTokenizeCardService(
        card_validator=MockCardValidator(),
        card_token_repository=SqlAlchemyCardRepository(session),
        card_encryptor=MockCardEncryptor(),
    )


def get_approve_card_payment_service(
    session: Session = Depends(get_db_session),
) -> ApproveCardPaymentService:
    return ApproveCardPaymentService(
        card_token_repository=SqlAlchemyCardRepository(session),
        card_transaction_repository=SqlAlchemyCardTransactionRepository(session),
    )
