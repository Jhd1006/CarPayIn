from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class VerifyAndTokenizeCardCommand:
    user_id: str
    card_number: str
    expiry: str
    cvc: str


@dataclass(frozen=True)
class VerifyAndTokenizeCardResult:
    card_token: str
    last_four: str


class VerifyAndTokenizeCardService:
    def __init__(
        self,
        card_validator,
        card_token_repository,
        card_encryptor,
    ):
        self.card_validator = card_validator
        self.card_token_repository = card_token_repository
        self.card_encryptor = card_encryptor

    def execute(
        self, command: VerifyAndTokenizeCardCommand
    ) -> VerifyAndTokenizeCardResult:
        if not self.card_validator.validate_card(
            command.card_number,
            command.expiry,
            command.cvc,
        ):
            raise ValueError("invalid_card")

        encrypted_card_num = self.card_encryptor.encrypt_card_number(
            command.card_number
        )
        existing = self.card_token_repository.get_by_user_and_encrypted_card(
            user_id=command.user_id,
            encrypted_card_num=encrypted_card_num,
        )
        if existing:
            return VerifyAndTokenizeCardResult(
                card_token=existing["card_token"],
                last_four=command.card_number[-4:],
            )

        expiry_month, expiry_year = command.expiry.split("/")
        card_token = f"card-token-{uuid.uuid4().hex[:12]}"
        last_four = command.card_number[-4:]

        self.card_token_repository.get_or_create_user(user_id=command.user_id)
        self.card_token_repository.save_card_with_token(
            user_id=command.user_id,
            encrypted_card_num=encrypted_card_num,
            cvc_hmac=self.card_encryptor.hash_cvc(command.cvc),
            exp_month=int(expiry_month),
            exp_year=2000 + int(expiry_year),
            card_token=card_token,
        )

        return VerifyAndTokenizeCardResult(
            card_token=card_token,
            last_four=last_four,
        )
