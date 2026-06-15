from dataclasses import dataclass
import logging

_logger = logging.getLogger("pms.handle_lpr_exit")


@dataclass(frozen=True)
class HandleLprExitCommand:
    lot_id: str
    plate: str


@dataclass(frozen=True)
class HandleLprExitResult:
    status: str
    pms_session_id: str | None


class HandleLprExitService:
    def __init__(self, pms_session_repository, barrier_publisher):
        self.pms_session_repository = pms_session_repository
        self.barrier_publisher = barrier_publisher

    def execute(self, command: HandleLprExitCommand) -> HandleLprExitResult:
        session = self.pms_session_repository.get_paid_session_by_lot_and_plate(
            lot_id=command.lot_id,
            plate=command.plate,
        )

        if session is None:
            _logger.info(
                "exit_lpr_not_paid: lot=%s plate=%s",
                command.lot_id, command.plate,
            )
            return HandleLprExitResult(status="not_paid", pms_session_id=None)

        pms_session_id = session["pms_session_id"]

        try:
            self.barrier_publisher.open_exit(pms_session_id=pms_session_id)
        except Exception as exc:
            _logger.warning("barrier_open_exit_failed: %s", exc)

        self.pms_session_repository.mark_exited(pms_session_id)
        _logger.info("exit_lpr_opened: pms_session_id=%s", pms_session_id)

        return HandleLprExitResult(status="opened", pms_session_id=pms_session_id)
