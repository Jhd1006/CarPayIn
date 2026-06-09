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
    def __init__(self, payment_request_repository, barrier_publisher, pms_session_repository=None):
        self.payment_request_repository = payment_request_repository
        self.barrier_publisher = barrier_publisher
        self.pms_session_repository = pms_session_repository

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
                self.pms_session_repository.mark_exited(command.pms_session_id)
                _logger.info("pms_session_exited: %s", command.pms_session_id)
            except LookupError:
                _logger.warning("session_not_found_on_payment: %s", command.pms_session_id)

        self.barrier_publisher.open_exit(pms_session_id=command.pms_session_id)
        return RecordPaymentCompleteResult(status="success")
