from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models import PMSParkingSession


class SqlAlchemyPmsSessionRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_session(
        self,
        *,
        pms_session_id: str,
        lot_id: str,
        plate: str,
        entry_time: str,
    ) -> dict:
        parking_session = PMSParkingSession(
            pms_session_id=pms_session_id,
            lot_id=lot_id,
            plate=plate,
            entry_time=datetime.fromisoformat(entry_time),
            status="active",
        )
        self.session.add(parking_session)
        self.session.commit()
        return self._to_dict(parking_session)

    def get_session_by_id(self, pms_session_id: str) -> dict | None:
        parking_session = self.session.get(PMSParkingSession, pms_session_id)
        return self._to_dict(parking_session) if parking_session is not None else None

    def get_active_session_by_plate(self, plate: str) -> dict | None:
        statement = select(PMSParkingSession).where(
            PMSParkingSession.plate == plate,
            PMSParkingSession.status == "active",
        )
        parking_session = self.session.scalar(statement)
        return self._to_dict(parking_session) if parking_session is not None else None

    def get_active_session_by_lot_and_plate(
        self, *, lot_id: str, plate: str
    ) -> dict | None:
        statement = select(PMSParkingSession).where(
            PMSParkingSession.lot_id == lot_id,
            PMSParkingSession.plate == plate,
            PMSParkingSession.status == "active",
        )
        parking_session = self.session.scalar(statement)
        return self._to_dict(parking_session) if parking_session is not None else None

    def update_status(self, pms_session_id: str, status: str) -> None:
        parking_session = self.session.get(PMSParkingSession, pms_session_id)
        if parking_session is None:
            raise LookupError("session_not_found")

        parking_session.status = status
        self.session.commit()

    @staticmethod
    def _to_dict(parking_session: PMSParkingSession) -> dict:
        return {
            "pms_session_id": parking_session.pms_session_id,
            "lot_id": parking_session.lot_id,
            "plate": parking_session.plate,
            "entry_time": parking_session.entry_time.isoformat(),
            "status": parking_session.status,
        }
