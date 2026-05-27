from uuid import uuid4

from app.infra.db.models import BillingKey, PGTransaction
from app.infra.db.session import SessionLocal
from app.infra.repositories.billing_key_repository import SqlAlchemyBillingKeyRepository
from app.infra.repositories.transaction_repository import SqlAlchemyTransactionRepository


def test_mock_pg_tables_can_store_and_load_data_from_postgres():
    session = SessionLocal()
    billing_key_repository = SqlAlchemyBillingKeyRepository(session)
    transaction_repository = SqlAlchemyTransactionRepository(session)

    unique_id = uuid4().hex
    order_id = f"integration-order-{unique_id}"
    billing_key = f"integration-bk-{unique_id}"
    transaction_id = f"integration-pg-tx-{unique_id}"
    idempotency_key = f"integration-pg-idempotency-{unique_id}"

    try:
        billing_key_repository.save_billing_key(
            order_id=order_id,
            billing_key=billing_key,
            card_token=f"integration-card-token-{unique_id}",
            last_four="1234",
        )
        assert billing_key_repository.get_by_order_id(order_id)["billing_key"] == billing_key
        assert billing_key_repository.get_billing_key(billing_key)["status"] == "active"

        transaction_repository.create_transaction(
            tx_id=transaction_id,
            idempotency_key=idempotency_key,
            billing_key=billing_key,
            amount=5000,
            currency="KRW",
            status="pending",
        )
        stored_transaction = transaction_repository.get_by_idempotency_key(
            idempotency_key
        )
        assert stored_transaction["card_token"] == f"integration-card-token-{unique_id}"
        assert stored_transaction["status"] == "pending"

        transaction_repository.update_transaction_status(
            idempotency_key,
            "success",
            approval_no="APPR1234",
            card_tx_id=f"integration-card-tx-{unique_id}",
        )
        updated_transaction = transaction_repository.get_by_idempotency_key(
            idempotency_key
        )
        assert updated_transaction["status"] == "success"
        assert updated_transaction["card_tx_id"] == f"integration-card-tx-{unique_id}"
    finally:
        session.rollback()
        transaction = session.get(PGTransaction, transaction_id)
        if transaction is not None:
            session.delete(transaction)
        key_record = session.get(BillingKey, billing_key)
        if key_record is not None:
            session.delete(key_record)
        session.commit()
        session.close()
