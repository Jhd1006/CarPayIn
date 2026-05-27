from sqlalchemy.orm import Session

from app.infra.db.models import VehicleBillingKey


class SqlAlchemyBillingKeyRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, *, car_id: str, billing_key: str, card_last_four: str) -> None:
        record = self.session.get(VehicleBillingKey, car_id)
        if record is None:
            record = VehicleBillingKey(car_id=car_id)
            self.session.add(record)

        record.billing_key = billing_key
        record.card_last_four = card_last_four
        record.status = "active"
        self.session.commit()

    def find_by_car_id(self, *, car_id: str) -> dict | None:
        record = self.session.get(VehicleBillingKey, car_id)
        return self._to_dict(record) if record is not None else None

    def has_active_billing_key(self, car_id: str) -> bool:
        return self.get_active_billing_key(car_id) is not None

    def get_active_billing_key(self, car_id: str) -> dict | None:
        record = self.session.get(VehicleBillingKey, car_id)
        if record is None or record.status != "active":
            return None
        return self._to_dict(record)

    @staticmethod
    def _to_dict(record: VehicleBillingKey) -> dict:
        return {
            "car_id": record.car_id,
            "billing_key": record.billing_key,
            "card_last_four": record.card_last_four,
            "status": record.status,
        }
