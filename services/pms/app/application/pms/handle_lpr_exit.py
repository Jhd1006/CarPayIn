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
    def __init__(self, pms_session_repository, barrier_publisher, parking_session_store=None):
        self.pms_session_repository = pms_session_repository
        self.barrier_publisher = barrier_publisher
        self.parking_session_store = parking_session_store

    def execute(self, command: HandleLprExitCommand) -> HandleLprExitResult:
        # Redis 우선 조회 (실시간 상태판)
        if self.parking_session_store is not None:
            cached = self.parking_session_store.get_session(lot_id=command.lot_id, plate=command.plate)
            if cached is not None:
                if cached["status"] == "paid":
                    return self._open_and_exit(cached["pms_session_id"], command, from_redis=True)
                _logger.info("exit_lpr_not_paid (redis): lot=%s plate=%s", command.lot_id, command.plate)
                return HandleLprExitResult(status="not_paid", pms_session_id=None)

        # DB fallback (Redis 재시작 등으로 키 유실된 경우)
        session = self.pms_session_repository.get_paid_session_by_lot_and_plate(
            lot_id=command.lot_id,
            plate=command.plate,
        )
        if session is not None:
            return self._open_and_exit(session["pms_session_id"], command, from_redis=False)

        _logger.info("exit_lpr_not_found: lot=%s plate=%s", command.lot_id, command.plate)
        return HandleLprExitResult(status="not_found", pms_session_id=None)

    def _open_and_exit(self, pms_session_id: str, command: HandleLprExitCommand, *, from_redis: bool) -> HandleLprExitResult:
        try:
            self.barrier_publisher.open_exit(pms_session_id=pms_session_id)
        except Exception as exc:
            _logger.warning("barrier_open_exit_failed: %s", exc)

        if from_redis and self.parking_session_store is not None:
            self.parking_session_store.delete_session(lot_id=command.lot_id, plate=command.plate)

        self.pms_session_repository.mark_exited(pms_session_id)
        _logger.info("exit_lpr_opened: pms_session_id=%s", pms_session_id)
        return HandleLprExitResult(status="opened", pms_session_id=pms_session_id)
