from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class ChargeBillingKeyCommand:
    billing_key: str
    amount: int
    currency: str
    idempotency_key: str


@dataclass(frozen=True)
class ChargeBillingKeyResult:
    status: str
    tx_id: str
    approval_no: str | None = None


class ChargeBillingKeyService:
    def __init__(
        self,
        billing_key_repository,
        transaction_repository,
        mock_card_client,
    ):
        self.billing_key_repository = billing_key_repository
        self.transaction_repository = transaction_repository
        self.mock_card_client = mock_card_client

    def execute(self, command: ChargeBillingKeyCommand) -> ChargeBillingKeyResult:
        # idempotency_key 중복 확인
        existing_tx = self.transaction_repository.get_by_idempotency_key(
            command.idempotency_key
        )
        if existing_tx:
            return ChargeBillingKeyResult(
                status=existing_tx["status"],
                tx_id=existing_tx["tx_id"],
                approval_no=existing_tx.get("approval_no"),
            )

        # billing key가 active인지 확인
        billing_key_data = self.billing_key_repository.get_billing_key(
            command.billing_key
        )
        if not billing_key_data:
            return ChargeBillingKeyResult(
                status="failed",
                tx_id=f"tx-{uuid.uuid4().hex[:12]}",
                approval_no=None,
            )

        if billing_key_data["status"] != "active":
            tx_id = f"tx-{uuid.uuid4().hex[:12]}"
            self.transaction_repository.create_transaction(
                tx_id=tx_id,
                idempotency_key=command.idempotency_key,
                billing_key=command.billing_key,
                amount=command.amount,
                currency=command.currency,
                status="failed",
                failed_reason="inactive_billing_key",
            )
            return ChargeBillingKeyResult(
                status="failed",
                tx_id=tx_id,
                approval_no=None,
            )

        # billing key로 card_token 찾기
        card_token = billing_key_data["card_token"]

        # pending transaction 생성
        tx_id = f"tx-{uuid.uuid4().hex[:12]}"
        self.transaction_repository.create_transaction(
            tx_id=tx_id,
            idempotency_key=command.idempotency_key,
            billing_key=command.billing_key,
            amount=command.amount,
            currency=command.currency,
            status="pending",
        )

        # Mock Card에 승인 요청
        try:
            approval_data = self.mock_card_client.approve_payment(
                card_token=card_token,
                amount=command.amount,
                currency=command.currency,
                idempotency_key=command.idempotency_key,
            )

            if approval_data.get("status", "success") != "success":
                self.transaction_repository.update_transaction_status(
                    command.idempotency_key,
                    "failed",
                    card_tx_id=approval_data.get("tx_id"),
                    failed_reason="card_payment_failed",
                )
                return ChargeBillingKeyResult(
                    status="failed",
                    tx_id=tx_id,
                    approval_no=None,
                )

            # 승인 성공 - transaction success로 업데이트
            approval_no = approval_data["approval_no"]
            self.transaction_repository.update_transaction_status(
                command.idempotency_key,
                "success",
                approval_no=approval_no,
                card_tx_id=approval_data.get("tx_id"),
            )

            return ChargeBillingKeyResult(
                status="success",
                tx_id=tx_id,
                approval_no=approval_no,
            )

        except Exception as exc:
            # 승인 실패 - transaction failed로 업데이트
            self.transaction_repository.update_transaction_status(
                command.idempotency_key,
                "failed",
                failed_reason=str(exc),
            )

            return ChargeBillingKeyResult(
                status="failed",
                tx_id=tx_id,
                approval_no=None,
            )
