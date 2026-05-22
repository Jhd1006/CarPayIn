from dataclasses import dataclass
import hashlib
import uuid


@dataclass(frozen=True)
class ProcessPaymentCommand:
    access_token: str
    session_id: str
    amount: int
    currency: str


@dataclass(frozen=True)
class ProcessPaymentResult:
    status: str
    tx_id: str
    session_id: str | None = None
    approval_no: str | None = None
    failed_reason: str | None = None
    amount: int | None = None
    currency: str | None = None


class ProcessPaymentService:
    def __init__(
        self,
        token_validator,
        fee_quote_store,
        parking_session_repository,
        billing_key_repository,
        transaction_repository,
        pg_client,
        pms_client,
        notification_publisher,
    ):
        self.token_validator = token_validator
        self.fee_quote_store = fee_quote_store
        self.parking_session_repository = parking_session_repository
        self.billing_key_repository = billing_key_repository
        self.transaction_repository = transaction_repository
        self.pg_client = pg_client
        self.pms_client = pms_client
        self.notification_publisher = notification_publisher

    def execute(self, command: ProcessPaymentCommand) -> ProcessPaymentResult:
        # 인증 및 car_id 추출
        token_data = self.token_validator.validate_and_extract(command.access_token)
        car_id = token_data["car_id"]

        # fee quote 조회
        quote = self.fee_quote_store.get_quote(command.session_id)
        if not quote:
            raise ValueError("quote_not_found")

        # amount/currency 검증
        if quote["amount"] != command.amount or quote["currency"] != command.currency:
            raise ValueError("amount_currency_mismatch")

        # parking session 조회
        session = self.parking_session_repository.get_session_by_id(command.session_id)
        if not session:
            raise ValueError("session_not_found")

        if session["car_id"] != car_id:
            raise ValueError("session_car_id_mismatch")

        # active billing key 조회
        billing_key_data = self.billing_key_repository.get_active_billing_key(car_id)
        if not billing_key_data:
            raise ValueError("no_active_billing_key")

        # idempotency_key 생성
        idempotency_key = hashlib.sha256(
            f"{command.session_id}{car_id}{command.amount}{command.currency}".encode()
        ).hexdigest()

        # 기존 transaction 확인
        existing_tx = self.transaction_repository.get_transaction_by_idempotency_key(
            idempotency_key
        )
        if existing_tx:
            return ProcessPaymentResult(
                status=existing_tx["status"],
                tx_id=existing_tx["tx_id"],
                approval_no=existing_tx.get("approval_no"),
                failed_reason=existing_tx.get("failed_reason"),
            )

        # pending transaction 생성
        tx_id = str(uuid.uuid4())
        self.transaction_repository.create_pending_transaction(
            tx_id=tx_id,
            idempotency_key=idempotency_key,
            session_id=command.session_id,
            amount=command.amount,
            currency=command.currency,
            billing_key=billing_key_data["billing_key"],
        )

        # PG 결제 요청
        try:
            pg_result = self.pg_client.charge_billing_key(
                billing_key=billing_key_data["billing_key"],
                amount=command.amount,
                currency=command.currency,
                idempotency_key=idempotency_key,
            )

            # PG 성공 처리
            if not pg_result.get("success", True):
                failed_reason = pg_result.get("failed_reason", "pg_payment_failed")
                self.transaction_repository.update_transaction_status(
                    idempotency_key, "failed", failed_reason=failed_reason
                )
                return ProcessPaymentResult(
                    status="failed",
                    tx_id=tx_id,
                    failed_reason=failed_reason,
                )

            approval_no = pg_result["approval_no"]
            self.transaction_repository.update_transaction_status(
                idempotency_key,
                "success",
                pg_tx_id=pg_result.get("pg_tx_id"),
                approval_no=approval_no,
            )
            self.parking_session_repository.update_session_status(
                command.session_id, "completed"
            )

            # PMS에 결제 완료 통보 (실패해도 결제는 성공 유지)
            try:
                self.pms_client.notify_payment_complete(
                    pms_session_id=session.get("pms_session_id", ""),
                    carpay_parking_session_id=command.session_id,
                    carpay_tx_id=tx_id,
                    amount=command.amount,
                    currency=command.currency,
                    approval_no=approval_no,
                    idempotency_key=idempotency_key,
                )
            except Exception:
                # PMS 통보 실패는 로그만 남기고 재시도 큐에 추가 (실제 구현에서)
                pass

            # 앱 알림 발행
            self.notification_publisher.publish_payment_notification(
                session_id=command.session_id,
                car_id=car_id,
                lot_id=session["lot_id"],
                tx_id=tx_id,
                amount=command.amount,
                currency=command.currency,
                approval_no=approval_no,
            )

            return ProcessPaymentResult(
                status="success",
                tx_id=tx_id,
                approval_no=approval_no,
            )

        except Exception as e:
            # PG 실패 처리
            failed_reason = str(e)
            self.transaction_repository.update_transaction_status(
                idempotency_key, "failed", failed_reason=failed_reason
            )

            return ProcessPaymentResult(
                status="failed",
                tx_id=tx_id,
                failed_reason=failed_reason,
            )
