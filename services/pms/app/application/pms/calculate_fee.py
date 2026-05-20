from dataclasses import dataclass


@dataclass(frozen=True)
class CalculateFeeCommand:
    pms_session_id: str
    current_time: str


@dataclass(frozen=True)
class CalculateFeeResult:
    amount: int
    duration_minutes: int
    currency: str


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
        session = self.pms_session_repository.get_session_by_id(
            command.pms_session_id
        )

        if not session:
            raise ValueError("session_not_found")

        if session["status"] != "active":
            raise ValueError("session_not_active")

        # 입차 시간과 요금 정책으로 amount, duration 계산
        fee_data = self.fee_calculator.calculate(
            entry_time=session["entry_time"],
            current_time=command.current_time,
        )

        return CalculateFeeResult(
            amount=fee_data["amount"],
            duration_minutes=fee_data["duration_minutes"],
            currency="KRW",
        )