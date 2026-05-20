from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class HandleLprEntryCommand:
    lot_id: str
    plate: str
    entry_time: str


@dataclass(frozen=True)
class HandleLprEntryResult:
    status: str
    pms_session_id: str


class HandleLprEntryService:
    def __init__(
        self,
        pms_session_repository,
        carpayin_webhook_client,
    ):
        self.pms_session_repository = pms_session_repository
        self.carpayin_webhook_client = carpayin_webhook_client

    def execute(self, command: HandleLprEntryCommand) -> HandleLprEntryResult:
        # 같은 plate에 active session이 있는지 확인
        existing_session = self.pms_session_repository.get_active_session_by_plate(
            command.plate
        )

        if existing_session:
            # 중복 생성하지 않고 기존 세션 반환
            return HandleLprEntryResult(
                status="existing",
                pms_session_id=existing_session["pms_session_id"],
            )

        # 새 PMS session 생성
        pms_session_id = f"pms-sess-{uuid.uuid4().hex[:12]}"
        self.pms_session_repository.create_session(
            pms_session_id=pms_session_id,
            lot_id=command.lot_id,
            plate=command.plate,
            entry_time=command.entry_time,
        )

        # CarPayIn Backend에 entry webhook 전송
        self.carpayin_webhook_client.send_entry_webhook(
            pms_session_id=pms_session_id,
            lot_id=command.lot_id,
            plate=command.plate,
            entry_time=command.entry_time,
        )

        return HandleLprEntryResult(
            status="created",
            pms_session_id=pms_session_id,
        )