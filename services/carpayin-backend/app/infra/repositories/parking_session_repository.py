from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models import ParkingSession


class SqlAlchemyParkingSessionRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_session(
        self,
        *,
        session_id: str,
        pms_session_id: str,
        car_id: str,
        plate: str,
        lot_id: str,
        entry_time: str,
    ) -> None:
        parking_session = ParkingSession(
            session_id=UUID(session_id),
            pms_session_id=pms_session_id,
            car_id=car_id,
            plate=plate,
            lot_id=lot_id,
            entry_time=datetime.fromisoformat(entry_time),
            status="active",
        )
        self.session.add(parking_session)
        self.session.commit()

    def get_session_by_id(self, session_id: str) -> dict | None:
        parking_session = self.session.get(ParkingSession, UUID(session_id))
        return self._to_dict(parking_session) if parking_session is not None else None

    def get_session_by_pms_session_id(self, pms_session_id: str) -> dict | None:
        statement = select(ParkingSession).where(
            ParkingSession.pms_session_id == pms_session_id
        )
        parking_session = self.session.scalar(statement)
        return self._to_dict(parking_session) if parking_session is not None else None

    def get_active_session_by_car_id(self, car_id: str) -> dict | None:
        statement = select(ParkingSession).where(
            ParkingSession.car_id == car_id,
            ParkingSession.status == "active",
        )
        parking_session = self.session.scalar(statement)
        return self._to_dict(parking_session) if parking_session is not None else None

    def update_session_status(self, session_id: str, status: str) -> None:
        parking_session = self.session.get(ParkingSession, UUID(session_id))
        if parking_session is None:
            raise LookupError("session_not_found")

        parking_session.status = status
        if status == "completed" and parking_session.exit_time is None:
            parking_session.exit_time = datetime.now(timezone.utc)
        self.session.commit()

    @staticmethod
    def _to_dict(parking_session: ParkingSession) -> dict:
        return {
            "session_id": str(parking_session.session_id),
            "pms_session_id": parking_session.pms_session_id,
            "car_id": parking_session.car_id,
            "lot_id": parking_session.lot_id,
            "plate": parking_session.plate,
            "entry_time": parking_session.entry_time.isoformat(),
            "exit_time": (
                parking_session.exit_time.isoformat()
                if parking_session.exit_time is not None
                else None
            ),
            "status": parking_session.status,
        }
