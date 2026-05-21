from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class ApproveCardPaymentCommand:
    card_token: str
    amount: int
    currency: str
    idempotency_key: str


@dataclass(frozen=True)
class ApproveCardPaymentResult:
    status: str
    tx_id: str
    approval_no: str | None = None


class ApproveCardPaymentService:
    def __init__(
        self,
        card_token_repository,
        card_transaction_repository,
    ):
        self.card_token_repository = card_token_repository
        self.card_transaction_repository = card_transaction_repository

    def execute(
        self, command: ApproveCardPaymentCommand
    ) -> ApproveCardPaymentResult:
        existing_tx = self.card_transaction_repository.get_by_idempotency_key(
            command.idempotency_key
        )
        if existing_tx:
            return ApproveCardPaymentResult(
                status=existing_tx["status"],
                tx_id=existing_tx["tx_id"],
                approval_no=existing_tx.get("approval_no"),
            )

        if command.amount <= 0:
            raise ValueError("invalid_amount")

        card_token_data = self.card_token_repository.get_card_token(
            command.card_token
        )
        if not card_token_data or card_token_data["status"] != "active":
            tx_id = f"card-tx-{uuid.uuid4().hex[:12]}"
            self.card_transaction_repository.create_transaction(
                tx_id=tx_id,
                idempotency_key=command.idempotency_key,
                card_token=command.card_token,
                amount=command.amount,
                currency=command.currency,
                status="failed",
            )

            return ApproveCardPaymentResult(
                status="failed",
                tx_id=tx_id,
                approval_no=None,
            )

        tx_id = f"card-tx-{uuid.uuid4().hex[:12]}"
        approval_no = f"CARD-{uuid.uuid4().hex[:8].upper()}"

        self.card_transaction_repository.create_transaction(
            tx_id=tx_id,
            idempotency_key=command.idempotency_key,
            card_token=command.card_token,
            amount=command.amount,
            currency=command.currency,
            status="success",
            approval_no=approval_no,
        )

        return ApproveCardPaymentResult(
            status="success",
            tx_id=tx_id,
            approval_no=approval_no,
        )
