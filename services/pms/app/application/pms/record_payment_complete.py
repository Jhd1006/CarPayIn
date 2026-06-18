from dataclasses import dataclass
import logging

_logger = logging.getLogger("pms.record_payment_complete")


@dataclass(frozen=True)
class RecordPaymentCompleteCommand:
    pms_session_id: str
    carpay_session_id: str
    tx_id: str
    amount: int
    currency: str
    approval_no: str
    idempotency_key: str


@dataclass(frozen=True)
class RecordPaymentCompleteResult:
    status: str


class RecordPaymentCompleteService:
    def __init__(self, payment_request_repository, pms_session_repository=None, barrier_publisher=None, parking_session_store=None):
        self.payment_request_repository = payment_request_repository
        self.pms_session_repository = pms_session_repository
        self.barrier_publisher = barrier_publisher
        self.parking_session_store = parking_session_store

    def execute(self, command: RecordPaymentCompleteCommand) -> RecordPaymentCompleteResult:
        existing = self.payment_request_repository.get_by_idempotency_key(command.idempotency_key)
        if existing:
            return RecordPaymentCompleteResult(status=existing["status"])

        self.payment_request_repository.save_payment_request(
            idempotency_key=command.idempotency_key,
            pms_session_id=command.pms_session_id,
            carpay_session_id=command.carpay_session_id,
            tx_id=command.tx_id,
            amount=command.amount,
            currency=command.currency,
            approval_no=command.approval_no,
        )

        if self.pms_session_repository is not None:
            try:
                session = self.pms_session_repository.get_session_by_id(command.pms_session_id)
                self.pms_session_repository.mark_paid(command.pms_session_id)
                _logger.info("pms_session_paid: %s", command.pms_session_id)
                if session and self.parking_session_store is not None:
                    self.parking_session_store.update_status(
                        lot_id=session["lot_id"],
                        plate=session["plate"],
                        status="paid",
                    )
            except LookupError:
                _logger.warning("session_not_found_on_payment: %s", command.pms_session_id)

        if self.barrier_publisher is not None:
            try:
                self.barrier_publisher.open_exit(pms_session_id=command.pms_session_id)
            except Exception as exc:
                _logger.warning("barrier_open_exit_failed: %s", exc)

        return RecordPaymentCompleteResult(status="success")
