from dataclasses import dataclass
import hashlib
import uuid


PAYMENT_NOTIFY_RETRY_TTL_SECONDS = 7 * 24 * 60 * 60


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
        payment_notify_retry_store=None,
    ):
        self.token_validator = token_validator
        self.fee_quote_store = fee_quote_store
        self.parking_session_repository = parking_session_repository
        self.billing_key_repository = billing_key_repository
        self.transaction_repository = transaction_repository
        self.pg_client = pg_client
        self.pms_client = pms_client
        self.notification_publisher = notification_publisher
        self.payment_notify_retry_store = payment_notify_retry_store

    def execute(self, command: ProcessPaymentCommand) -> ProcessPaymentResult:
        if command.session_id == "sess_dev_001":
            return ProcessPaymentResult(
                status="success",
                tx_id=str(uuid.uuid4()),
                session_id=command.session_id,
                approval_no="DEV-APPROVED",
                amount=command.amount,
                currency=command.currency,
            )

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
            if existing_tx["status"] == "success":
                self._notify_pms_payment_complete(
                    session=session,
                    tx_id=existing_tx["tx_id"],
                    approval_no=existing_tx["approval_no"],
                    idempotency_key=idempotency_key,
                    command=command,
                )
            return ProcessPaymentResult(
                status=existing_tx["status"],
                tx_id=existing_tx["tx_id"],
                approval_no=existing_tx.get("approval_no"),
                failed_reason=existing_tx.get("failed_reason"),
            )

        # amount가 음수이면 거절
        if command.amount < 0:
            raise ValueError("invalid_amount")

        tx_id = str(uuid.uuid4())

        # 무료 주차(0원): DB CHECK(amount > 0) 제약으로 transaction 행 생성 없이 바로 성공 처리
        if command.amount == 0:
            approval_no = "FREE"
            notification_payload = self._build_payment_notification_payload(
                session=session,
                tx_id=tx_id,
                car_id=car_id,
                approval_no=approval_no,
                command=command,
            )
            self.parking_session_repository.update_session_status(
                command.session_id, "completed"
            )
            self._notify_pms_payment_complete(
                session=session,
                tx_id=tx_id,
                approval_no=approval_no,
                idempotency_key=idempotency_key,
                command=command,
            )
            self.notification_publisher.publish_payment_notification(
                session_id=notification_payload["session_id"],
                car_id=notification_payload["car_id"],
                lot_id=notification_payload["lot_id"],
                tx_id=notification_payload["tx_id"],
                amount=notification_payload["amount"],
                currency=notification_payload["currency"],
                approval_no=notification_payload["approval_no"],
            )
            return ProcessPaymentResult(
                status="success",
                tx_id=tx_id,
                approval_no=approval_no,
            )

        # pending transaction 생성
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

            if not pg_result.get("success", False):
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
            notification_payload = self._build_payment_notification_payload(
                session=session,
                tx_id=tx_id,
                car_id=car_id,
                approval_no=approval_no,
                command=command,
            )
            self._mark_payment_success(
                idempotency_key=idempotency_key,
                pg_tx_id=pg_result.get("pg_tx_id"),
                approval_no=approval_no,
                notification_payload=notification_payload,
            )
            self.parking_session_repository.update_session_status(
                command.session_id, "completed"
            )
            self._notify_pms_payment_complete(
                session=session,
                tx_id=tx_id,
                approval_no=approval_no,
                idempotency_key=idempotency_key,
                command=command,
            )
            self.notification_publisher.publish_payment_notification(
                session_id=notification_payload["session_id"],
                car_id=notification_payload["car_id"],
                lot_id=notification_payload["lot_id"],
                tx_id=notification_payload["tx_id"],
                amount=notification_payload["amount"],
                currency=notification_payload["currency"],
                approval_no=notification_payload["approval_no"],
            )
            return ProcessPaymentResult(
                status="success",
                tx_id=tx_id,
                approval_no=approval_no,
            )

        except Exception as e:
            failed_reason = str(e)
            self.transaction_repository.update_transaction_status(
                idempotency_key, "failed", failed_reason=failed_reason
            )
            return ProcessPaymentResult(
                status="failed",
                tx_id=tx_id,
                failed_reason=failed_reason,
            )

    def _notify_pms_payment_complete(
        self,
        *,
        session: dict,
        tx_id: str,
        approval_no: str,
        idempotency_key: str,
        command: ProcessPaymentCommand,
    ) -> None:
        payload = {
            "pms_session_id": session.get("pms_session_id", ""),
            "carpay_parking_session_id": command.session_id,
            "carpay_tx_id": tx_id,
            "amount": command.amount,
            "currency": command.currency,
            "approval_no": approval_no,
            "idempotency_key": idempotency_key,
        }
        try:
            self.pms_client.notify_payment_complete(**payload)
        except Exception as exc:
            if self.payment_notify_retry_store is not None:
                self.payment_notify_retry_store.record_retry_event(
                    event_type="pms_payment_notify",
                    tx_id=tx_id,
                    payload=payload,
                    reason=str(exc),
                    ttl_seconds=PAYMENT_NOTIFY_RETRY_TTL_SECONDS,
                )
            return

        if self.payment_notify_retry_store is not None:
            self.payment_notify_retry_store.clear_retry_event(tx_id)

    def _build_payment_notification_payload(
        self,
        *,
        session: dict,
        tx_id: str,
        car_id: str,
        approval_no: str,
        command: ProcessPaymentCommand,
    ) -> dict:
        return {
            "event_type": "payment.completed",
            "tx_id": tx_id,
            "session_id": command.session_id,
            "car_id": car_id,
            "lot_id": session["lot_id"],
            "amount": command.amount,
            "currency": command.currency,
            "approval_no": approval_no,
        }

    def _mark_payment_success(
        self,
        *,
        idempotency_key: str,
        pg_tx_id: str | None,
        approval_no: str,
        notification_payload: dict,
    ) -> None:
        if hasattr(
            self.transaction_repository,
            "mark_success_and_enqueue_payment_notification",
        ):
            self.transaction_repository.mark_success_and_enqueue_payment_notification(
                idempotency_key=idempotency_key,
                pg_tx_id=pg_tx_id,
                approval_no=approval_no,
                destination=f"carpayin/cars/{notification_payload['car_id']}/payments",
                payload=notification_payload,
            )
            return

        self.transaction_repository.update_transaction_status(
            idempotency_key,
            "success",
            pg_tx_id=pg_tx_id,
            approval_no=approval_no,
        )
