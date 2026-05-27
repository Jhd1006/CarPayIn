from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models import BillingKey


class SqlAlchemyBillingKeyRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_billing_key(
        self, *, order_id: str, billing_key: str, card_token: str, last_four: str
    ) -> dict:
        existing = self.get_by_order_id(order_id)
        if existing is not None:
            return existing

        record = BillingKey(
            order_id=order_id,
            billing_key=billing_key,
            card_token=card_token,
            card_last_four=last_four,
            status="active",
        )
        self.session.add(record)
        self.session.commit()
        return self._to_dict(record)

    def get_by_order_id(self, order_id: str) -> dict | None:
        statement = select(BillingKey).where(BillingKey.order_id == order_id)
        record = self.session.scalar(statement)
        return self._to_dict(record) if record is not None else None

    def get_billing_key(self, billing_key: str) -> dict | None:
        record = self.session.get(BillingKey, billing_key)
        return self._to_dict(record) if record is not None else None

    @staticmethod
    def _to_dict(record: BillingKey) -> dict:
        return {
            "billing_key": record.billing_key,
            "order_id": record.order_id,
            "card_token": record.card_token,
            "last_four": record.card_last_four,
            "status": record.status,
        }
