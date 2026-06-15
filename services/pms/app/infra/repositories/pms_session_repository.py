from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models import PMSParkingSession


class SqlAlchemyPmsSessionRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_session(self, *, pms_session_id, lot_id, plate, entry_time):
        obj = PMSParkingSession(
            pms_session_id=pms_session_id,
            lot_id=lot_id,
            plate=plate,
            entry_time=datetime.fromisoformat(entry_time),
            status="active",
        )
        self.session.add(obj)
        self.session.commit()
        return self._to_dict(obj)

    def get_session_by_id(self, pms_session_id):
        obj = self.session.get(PMSParkingSession, pms_session_id)
        return self._to_dict(obj) if obj else None

    def get_active_session_by_plate(self, plate):
        stmt = select(PMSParkingSession).where(
            PMSParkingSession.plate == plate,
            PMSParkingSession.status == "active",
        )
        obj = self.session.scalar(stmt)
        return self._to_dict(obj) if obj else None

    def get_paid_session_by_lot_and_plate(self, *, lot_id, plate):
        stmt = select(PMSParkingSession).where(
            PMSParkingSession.lot_id == lot_id,
            PMSParkingSession.plate == plate,
            PMSParkingSession.status == "paid",
        )
        obj = self.session.scalar(stmt)
        return self._to_dict(obj) if obj else None

    def get_active_session_by_lot_and_plate(self, *, lot_id, plate):
        stmt = select(PMSParkingSession).where(
            PMSParkingSession.lot_id == lot_id,
            PMSParkingSession.plate == plate,
            PMSParkingSession.status == "active",
        )
        obj = self.session.scalar(stmt)
        return self._to_dict(obj) if obj else None

    def update_status(self, pms_session_id, status):
        obj = self.session.get(PMSParkingSession, pms_session_id)
        if obj is None:
            raise LookupError("session_not_found")
        obj.status = status
        self.session.commit()

    def mark_paid(self, pms_session_id):
        """결제 완료 통보 수신 시 paid 상태로 변경. 출차 LPR에서 exited로 전환."""
        obj = self.session.get(PMSParkingSession, pms_session_id)
        if obj is None:
            raise LookupError("session_not_found")
        obj.status = "paid"
        self.session.commit()

    def mark_exited(self, pms_session_id):
        """출차 LPR 확인 후 exited 상태 + exit_time 기록."""
        obj = self.session.get(PMSParkingSession, pms_session_id)
        if obj is None:
            raise LookupError("session_not_found")
        obj.status = "exited"
        obj.exit_time = datetime.now(timezone.utc)
        self.session.commit()

    @staticmethod
    def _to_dict(obj):
        return {
            "pms_session_id": obj.pms_session_id,
            "lot_id": obj.lot_id,
            "plate": obj.plate,
            "entry_time": obj.entry_time.isoformat(),
            "exit_time": obj.exit_time.isoformat() if obj.exit_time else None,
            "status": obj.status,
        }
