from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models import BillingKey, PGTransaction


class SqlAlchemyTransactionRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_transaction(
        self,
        *,
        tx_id: str,
        idempotency_key: str,
        billing_key: str,
        amount: int,
        currency: str,
        status: str,
        approval_no: str | None = None,
        failed_reason: str | None = None,
    ) -> dict:
        existing = self.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        key_record = self.session.get(BillingKey, billing_key)
        if key_record is None:
            raise LookupError("billing_key_not_found")

        transaction = PGTransaction(
            pg_tx_id=tx_id,
            idempotency_key=idempotency_key,
            billing_key=billing_key,
            card_token=key_record.card_token,
            amount=amount,
            currency=currency,
            status=status,
            approval_no=approval_no,
            failed_reason=failed_reason,
        )
        self.session.add(transaction)
        self.session.commit()
        return self._to_dict(transaction)

    def get_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        statement = select(PGTransaction).where(
            PGTransaction.idempotency_key == idempotency_key
        )
        transaction = self.session.scalar(statement)
        return self._to_dict(transaction) if transaction is not None else None

    def update_transaction_status(
        self,
        idempotency_key: str,
        status: str,
        approval_no: str | None = None,
        card_tx_id: str | None = None,
        failed_reason: str | None = None,
    ) -> None:
        statement = select(PGTransaction).where(
            PGTransaction.idempotency_key == idempotency_key
        )
        transaction = self.session.scalar(statement)
        if transaction is None:
            raise LookupError("transaction_not_found")

        transaction.status = status
        transaction.approval_no = approval_no
        transaction.card_tx_id = card_tx_id
        transaction.failed_reason = failed_reason
        self.session.commit()

    @staticmethod
    def _to_dict(transaction: PGTransaction) -> dict:
        return {
            "tx_id": transaction.pg_tx_id,
            "billing_key": transaction.billing_key,
            "card_token": transaction.card_token,
            "card_tx_id": transaction.card_tx_id,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "status": transaction.status,
            "approval_no": transaction.approval_no,
            "idempotency_key": transaction.idempotency_key,
            "failed_reason": transaction.failed_reason,
        }
