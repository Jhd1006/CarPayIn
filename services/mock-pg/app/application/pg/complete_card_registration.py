from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class CompleteCardRegistrationCommand:
    order_id: str
    card_number: str
    expiry: str
    cvc: str


@dataclass(frozen=True)
class CompleteCardRegistrationResult:
    status: str
    billing_key: str | None = None


class CompleteCardRegistrationService:
    def __init__(
        self,
        mock_card_client,
        billing_key_repository,
        carpayin_webhook_client,
        allow_local_fallback: bool = False,
    ):
        self.mock_card_client = mock_card_client
        self.billing_key_repository = billing_key_repository
        self.carpayin_webhook_client = carpayin_webhook_client
        self.allow_local_fallback = allow_local_fallback

    def execute(
        self, command: CompleteCardRegistrationCommand
    ) -> CompleteCardRegistrationResult:
        existing = self.billing_key_repository.get_by_order_id(command.order_id)
        if existing:
            self.carpayin_webhook_client.send_card_registration_webhook(
                order_id=command.order_id,
                billing_key=existing["billing_key"],
                last_four=existing["last_four"],
            )
            return CompleteCardRegistrationResult(
                status="success",
                billing_key=existing["billing_key"],
            )

        try:
            card_data = self.mock_card_client.verify_and_tokenize_card(
                user_id=command.order_id,
                card_number=command.card_number,
                expiry=command.expiry,
                cvc=command.cvc,
            )
        except Exception:
            if not self.allow_local_fallback:
                return CompleteCardRegistrationResult(
                    status="failed",
                    billing_key=None,
                )
            card_data = {
                "card_token": f"local-card-token-{uuid.uuid4().hex[:12]}",
                "last_four": self._last_four_or_default(command.card_number),
            }

        billing_key = f"bk-{uuid.uuid4().hex[:12]}"
        self.billing_key_repository.save_billing_key(
            order_id=command.order_id,
            billing_key=billing_key,
            card_token=card_data["card_token"],
            last_four=card_data["last_four"],
        )

        self.carpayin_webhook_client.send_card_registration_webhook(
            order_id=command.order_id,
            billing_key=billing_key,
            last_four=card_data["last_four"],
        )

        return CompleteCardRegistrationResult(
            status="success",
            billing_key=billing_key,
        )

    @staticmethod
    def _last_four_or_default(card_number: str) -> str:
        digits = "".join(ch for ch in str(card_number or "") if ch in "0123456789")
        return (digits[-4:] if digits else "0000").rjust(4, "0")
