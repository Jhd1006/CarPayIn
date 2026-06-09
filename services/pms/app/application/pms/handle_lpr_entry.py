from dataclasses import dataclass
import logging
import uuid

_logger = logging.getLogger("pms.handle_lpr_entry")


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
        pre_registration_repository,
        pms_session_repository,
        carpayin_webhook_client,
        barrier_publisher=None,
    ):
        self.pre_registration_repository = pre_registration_repository
        self.pms_session_repository = pms_session_repository
        self.carpayin_webhook_client = carpayin_webhook_client
        self.barrier_publisher = barrier_publisher

    def execute(self, command: HandleLprEntryCommand) -> HandleLprEntryResult:
        # LPR 인식 즉시 입구 차단기 개방 (사전등록 여부와 무관)
        if self.barrier_publisher is not None:
            try:
                self.barrier_publisher.open_entry(pms_session_id="")
            except Exception as exc:
                _logger.warning("barrier_open_entry_failed: %s", exc)

        # 같은 plate에 active session이 있는지 확인
        existing_session = self.pms_session_repository.get_active_session_by_plate(
            command.plate
        )

        if existing_session:
            self.carpayin_webhook_client.send_entry_webhook(
                pms_session_id=existing_session["pms_session_id"],
                lot_id=existing_session["lot_id"],
                plate=existing_session["plate"],
                entry_time=existing_session["entry_time"],
            )
            # 중복 생성하지 않고 기존 세션 반환
            return HandleLprEntryResult(
                status="existing",
                pms_session_id=existing_session["pms_session_id"],
            )

        registration = self.pre_registration_repository.get_active_pre_registration(
            lot_id=command.lot_id,
            plate=command.plate,
        )
        if registration is None:
            raise ValueError("pre_registration_not_found")

        # 새 PMS session 생성
        pms_session_id = f"pms-sess-{uuid.uuid4().hex[:12]}"
        self.pms_session_repository.create_session(
            pms_session_id=pms_session_id,
            lot_id=command.lot_id,
            plate=command.plate,
            entry_time=command.entry_time,
        )
        self.pre_registration_repository.consume_pre_registration(
            lot_id=command.lot_id,
            plate=command.plate,
        )

        # CarPayIn Backend에 entry webhook 전송 (실패해도 PMS 세션은 유지)
        try:
            self.carpayin_webhook_client.send_entry_webhook(
                pms_session_id=pms_session_id,
                lot_id=command.lot_id,
                plate=command.plate,
                entry_time=command.entry_time,
            )
        except Exception as exc:
            _logger.warning(
                "carpayin_webhook_failed_but_session_created: %s (pms_session_id=%s)",
                exc, pms_session_id,
            )

        return HandleLprEntryResult(
            status="created",
            pms_session_id=pms_session_id,
        )
