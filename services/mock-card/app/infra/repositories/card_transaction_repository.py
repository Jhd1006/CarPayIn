from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models import Tx


class SqlAlchemyCardTransactionRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_transaction(
        self,
        *,
        tx_id: str,
        idempotency_key: str,
        card_token: str,
        amount: int,
        currency: str,
        status: str,
        approval_no: str | None = None,
    ) -> dict:
        existing = self.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        transaction = Tx(
            tx_id=tx_id,
            idempotency_key=idempotency_key,
            card_token=card_token,
            amount=amount,
            currency=currency,
            status=status,
            approval_no=approval_no,
        )
        self.session.add(transaction)
        self.session.commit()
        return self._to_dict(transaction)

    def get_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        statement = select(Tx).where(Tx.idempotency_key == idempotency_key)
        transaction = self.session.scalar(statement)
        return self._to_dict(transaction) if transaction is not None else None

    @staticmethod
    def _to_dict(transaction: Tx) -> dict:
        return {
            "tx_id": transaction.tx_id,
            "card_token": transaction.card_token,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "status": transaction.status,
            "approval_no": transaction.approval_no,
            "idempotency_key": transaction.idempotency_key,
        }