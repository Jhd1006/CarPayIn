from dataclasses import dataclass


@dataclass(frozen=True)
class RegisterPreNotifyCommand:
    lot_id: str
    plate: str


@dataclass(frozen=True)
class RegisterPreNotifyResult:
    status: str
    lot_id: str
    plate: str


class RegisterPreNotifyService:
    def __init__(self, pre_registration_repository):
        self.pre_registration_repository = pre_registration_repository

    def execute(self, command: RegisterPreNotifyCommand) -> RegisterPreNotifyResult:
        # lot_id와 plate를 사전 등록 상태로 저장
        # 중복 등록이면 기존 등록을 재사용
        registration = self.pre_registration_repository.save_pre_registration(
            lot_id=command.lot_id,
            plate=command.plate,
        )

        return RegisterPreNotifyResult(
            status="registered",
            lot_id=registration["lot_id"],
            plate=registration["plate"],
        )