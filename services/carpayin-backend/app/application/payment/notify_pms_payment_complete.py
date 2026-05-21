from dataclasses import dataclass


@dataclass(frozen=True)
class NotifyPmsPaymentCompleteCommand:
    pms_session_id: str
    carpay_parking_session_id: str
    carpay_tx_id: str
    amount: int
    currency: str
    approval_no: str
    idempotency_key: str


@dataclass(frozen=True)
class NotifyPmsPaymentCompleteResult:
    status: str
    retry_reason: str | None = None


class NotifyPmsPaymentCompleteService:
    def __init__(
        self,
        transaction_repository,
        pms_client,
        retry_event_store,
    ):
        self.transaction_repository = transaction_repository
        self.pms_client = pms_client
        self.retry_event_store = retry_event_store

    def execute(
        self, command: NotifyPmsPaymentCompleteCommand
    ) -> NotifyPmsPaymentCompleteResult:
        # transaction success 상태 확인 (사전 조건)
        tx = self.transaction_repository.get_transaction_by_id(command.carpay_tx_id)
        if not tx or tx["status"] != "success":
            raise ValueError("transaction_not_success")

        # PMS에 결제 완료 통보
        try:
            response = self.pms_client.notify_payment_complete(
                pms_session_id=command.pms_session_id,
                carpay_parking_session_id=command.carpay_parking_session_id,
                carpay_tx_id=command.carpay_tx_id,
                amount=command.amount,
                currency=command.currency,
                approval_no=command.approval_no,
                idempotency_key=command.idempotency_key,
            )

            # PMS idempotency conflict 처리
            if response.get("status") == "conflict":
                return NotifyPmsPaymentCompleteResult(
                    status="already_processed",
                )

            return NotifyPmsPaymentCompleteResult(status="success")

        except (TimeoutError, Exception) as e:
            # PMS 통보 실패 시 재시도 이벤트 기록
            reason = str(e)
            self.retry_event_store.record_retry_event(
                event_type="pms_payment_notify",
                tx_id=command.carpay_tx_id,
                payload={
                    "pms_session_id": command.pms_session_id,
                    "carpay_parking_session_id": command.carpay_parking_session_id,
                    "amount": command.amount,
                    "currency": command.currency,
                    "approval_no": command.approval_no,
                    "idempotency_key": command.idempotency_key,
                },
                reason=reason,
            )

            return NotifyPmsPaymentCompleteResult(
                status="retry_scheduled",
                retry_reason=reason,
            )
