from uuid import uuid4

from app.infra.db.models import Card, CardToken, Tx, User
from app.infra.db.session import SessionLocal
from app.infra.repositories.card_repository import SqlAlchemyCardRepository
from app.infra.repositories.card_transaction_repository import (
    SqlAlchemyCardTransactionRepository,
)


def test_mock_card_tables_can_store_and_load_data_from_postgres():
    session = SessionLocal()
    card_repository = SqlAlchemyCardRepository(session)
    transaction_repository = SqlAlchemyCardTransactionRepository(session)

    unique_id = uuid4().hex
    user_id = f"integration-card-user-{unique_id}"
    encrypted_card_num = f"encrypted-{unique_id}"
    card_token = f"integration-card-token-{unique_id}"
    transaction_id = f"integration-card-tx-{unique_id}"
    idempotency_key = f"integration-card-idempotency-{unique_id}"

    try:
        card_repository.get_or_create_user(user_id=user_id)
        stored_token = card_repository.save_card_with_token(
            user_id=user_id,
            encrypted_card_num=encrypted_card_num,
            cvc_hmac=f"hmac-{unique_id}",
            exp_month=12,
            exp_year=2028,
            card_token=card_token,
        )
        assert stored_token["status"] == "active"
        assert (
            card_repository.get_by_user_and_encrypted_card(
                user_id=user_id, encrypted_card_num=encrypted_card_num
            )["card_token"]
            == card_token
        )

        transaction_repository.create_transaction(
            tx_id=transaction_id,
            idempotency_key=idempotency_key,
            card_token=card_token,
            amount=5000,
            currency="KRW",
            status="success",
            approval_no="CARD1234",
        )
        stored_transaction = transaction_repository.get_by_idempotency_key(
            idempotency_key
        )
        assert stored_transaction["card_token"] == card_token
        assert stored_transaction["status"] == "success"
    finally:
        session.rollback()
        transaction = session.get(Tx, transaction_id)
        if transaction is not None:
            session.delete(transaction)
        token = session.get(CardToken, card_token)
        card_id = token.card_id if token is not None else None
        if token is not None:
            session.delete(token)
        session.flush()
        if card_id is not None:
            card = session.get(Card, card_id)
            if card is not None:
                session.delete(card)
        user = session.get(User, user_id)
        if user is not None:
            session.delete(user)
        session.commit()
        session.close()
