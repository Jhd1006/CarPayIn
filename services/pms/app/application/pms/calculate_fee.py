from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class CalculateFeeCommand:
    pms_session_id: str | None = None
    current_time: str | None = None
    lot_id: str | None = None
    plate: str | None = None


@dataclass(frozen=True)
class CalculateFeeResult:
    amount: int
    duration_minutes: int | None
    currency: str
    pms_session_id: str | None = None
    lot_id: str | None = None
    plate: str | None = None
    entry_time: str | None = None
    calculated_at: str | None = None


class CalculateFeeService:
    def __init__(
        self,
        pms_session_repository,
        fee_calculator,
    ):
        self.pms_session_repository = pms_session_repository
        self.fee_calculator = fee_calculator

    def execute(self, command: CalculateFeeCommand) -> CalculateFeeResult:
        # active PMS session 찾기
        session = self._find_session(command)

        if not session:
            raise ValueError("session_not_found")

        if session["status"] != "active":
            raise ValueError("session_not_active")

        current_time = command.current_time or datetime.now(timezone.utc).isoformat()

        # 입차 시간과 요금 정책으로 amount, duration 계산
        fee_data = self.fee_calculator.calculate(
            entry_time=session["entry_time"],
            current_time=current_time,
        )

        return CalculateFeeResult(
            amount=fee_data["amount"],
            duration_minutes=fee_data["duration_minutes"],
            currency="KRW",
            pms_session_id=session.get("pms_session_id"),
            lot_id=session.get("lot_id"),
            plate=session.get("plate"),
            entry_time=session.get("entry_time"),
            calculated_at=current_time,
        )

    def _find_session(self, command: CalculateFeeCommand):
        # 1차: lot_id + plate 조합으로 조회
        if command.lot_id and command.plate:
            finder = getattr(
                self.pms_session_repository,
                "get_active_session_by_lot_and_plate",
                None,
            )
            if finder:
                session = finder(lot_id=command.lot_id, plate=command.plate)
                if session is not None:
                    return session

        # 2차 폴백: pms_session_id로 조회 (lot+plate 조회 실패 시에도 시도)
        if command.pms_session_id:
            return self.pms_session_repository.get_session_by_id(
                command.pms_session_id
            )

        return None
