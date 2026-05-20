from dataclasses import dataclass


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
    def __init__(self, payment_request_repository):
        self.payment_request_repository = payment_request_repository

    def execute(
        self, command: RecordPaymentCompleteCommand
    ) -> RecordPaymentCompleteResult:
        # idempotency_key로 중복 확인
        existing = self.payment_request_repository.get_by_idempotency_key(
            command.idempotency_key
        )

        if existing:
            # 기존 결과 반환
            return RecordPaymentCompleteResult(status=existing["status"])

        # PMS DB payment_requests에 success 이력 저장
        self.payment_request_repository.save_payment_request(
            idempotency_key=command.idempotency_key,
            pms_session_id=command.pms_session_id,
            carpay_session_id=command.carpay_session_id,
            tx_id=command.tx_id,
            amount=command.amount,
            currency=command.currency,
            approval_no=command.approval_no,
        )

        return RecordPaymentCompleteResult(status="success")