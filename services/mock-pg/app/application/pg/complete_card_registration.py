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
    ):
        self.mock_card_client = mock_card_client
        self.billing_key_repository = billing_key_repository
        self.carpayin_webhook_client = carpayin_webhook_client

    def execute(
        self, command: CompleteCardRegistrationCommand
    ) -> CompleteCardRegistrationResult:
        # 같은 order_id로 이미 생성된 billing_key 확인
        existing = self.billing_key_repository.get_by_order_id(command.order_id)
        if existing:
            return CompleteCardRegistrationResult(
                status="success",
                billing_key=existing["billing_key"],
            )

        # Mock Card에 카드 검증과 token 생성 요청
        try:
            card_data = self.mock_card_client.verify_and_tokenize_card(
                card_number=command.card_number,
                expiry=command.expiry,
                cvc=command.cvc,
            )
        except Exception:
            # 카드 검증 실패
            return CompleteCardRegistrationResult(
                status="failed",
                billing_key=None,
            )

        # 받은 card_token으로 billing_key 생성
        billing_key = f"bk-{uuid.uuid4().hex[:12]}"
        self.billing_key_repository.save_billing_key(
            order_id=command.order_id,
            billing_key=billing_key,
            card_token=card_data["card_token"],
            last_four=card_data["last_four"],
        )

        # CarPayIn Backend에 card webhook 전송
        self.carpayin_webhook_client.send_card_registration_webhook(
            order_id=command.order_id,
            billing_key=billing_key,
            last_four=card_data["last_four"],
        )

        return CompleteCardRegistrationResult(
            status="success",
            billing_key=billing_key,
        )