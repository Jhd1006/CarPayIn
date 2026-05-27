from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.infra.db.models import PreRegistration


class SqlAlchemyPreRegistrationRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_pre_registration(self, *, lot_id: str, plate: str) -> dict:
        registration = self.session.get(PreRegistration, (lot_id, plate))
        if registration is None:
            registration = PreRegistration(lot_id=lot_id, plate=plate)
            self.session.add(registration)
        else:
            registration.status = "pre_registered"
            registration.registered_at = datetime.now(timezone.utc)
            registration.consumed_at = None

        self.session.commit()
        return self._to_dict(registration)

    def get_active_pre_registration(self, *, lot_id: str, plate: str) -> dict | None:
        registration = self.session.get(PreRegistration, (lot_id, plate))
        if registration is None or registration.status != "pre_registered":
            return None
        return self._to_dict(registration)

    def consume_pre_registration(self, *, lot_id: str, plate: str) -> None:
        registration = self.session.get(PreRegistration, (lot_id, plate))
        if registration is None or registration.status != "pre_registered":
            raise LookupError("pre_registration_not_found")

        registration.status = "consumed"
        registration.consumed_at = datetime.now(timezone.utc)
        self.session.commit()

    @staticmethod
    def _to_dict(registration: PreRegistration) -> dict:
        return {
            "lot_id": registration.lot_id,
            "plate": registration.plate,
            "status": registration.status,
            "registered_at": registration.registered_at,
            "consumed_at": registration.consumed_at,
        }
