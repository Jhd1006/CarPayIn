from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models import ParkingSession, Transaction


class SqlAlchemyTransactionRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_pending_transaction(
        self,
        *,
        tx_id: str,
        idempotency_key: str,
        session_id: str,
        amount: int,
        currency: str,
        billing_key: str,
    ) -> None:
        parking_session_id = UUID(session_id)
        parking_session = self.session.get(ParkingSession, parking_session_id)
        if parking_session is None:
            raise LookupError("session_not_found")

        transaction = Transaction(
            tx_id=UUID(tx_id),
            idempotency_key=idempotency_key,
            session_id=parking_session_id,
            car_id=parking_session.car_id,
            amount=amount,
            currency=currency,
            billing_key=billing_key,
            status="pending",
        )
        self.session.add(transaction)
        self.session.commit()

    def get_transaction_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        statement = select(Transaction).where(
            Transaction.idempotency_key == idempotency_key
        )
        transaction = self.session.scalar(statement)
        return self._to_dict(transaction) if transaction is not None else None

    def get_transaction_by_id(self, tx_id: str) -> dict | None:
        transaction = self.session.get(Transaction, UUID(tx_id))
        return self._to_dict(transaction) if transaction is not None else None

    def update_transaction_status(
        self,
        idempotency_key: str,
        status: str,
        pg_tx_id: str | None = None,
        approval_no: str | None = None,
        failed_reason: str | None = None,
    ) -> None:
        statement = select(Transaction).where(
            Transaction.idempotency_key == idempotency_key
        )
        transaction = self.session.scalar(statement)
        if transaction is None:
            raise LookupError("transaction_not_found")

        transaction.status = status
        transaction.pg_tx_id = pg_tx_id
        transaction.approval_no = approval_no
        transaction.failed_reason = failed_reason
        self.session.commit()

    @staticmethod
    def _to_dict(transaction: Transaction) -> dict:
        return {
            "tx_id": str(transaction.tx_id),
            "session_id": str(transaction.session_id),
            "car_id": transaction.car_id,
            "billing_key": transaction.billing_key,
            "pg_tx_id": transaction.pg_tx_id,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "status": transaction.status,
            "approval_no": transaction.approval_no,
            "idempotency_key": transaction.idempotency_key,
            "failed_reason": transaction.failed_reason,
        }
