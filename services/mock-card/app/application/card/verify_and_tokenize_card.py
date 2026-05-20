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
        # 카드번호, 유효기간, CVC 검증
        is_valid = self.card_validator.validate_card(
            command.card_number, command.expiry, command.cvc
        )

        if not is_valid:
            raise ValueError("invalid_card")

        # 같은 사용자와 카드의 중복 등록 확인
        existing = self.card_token_repository.get_by_user_and_card(
            command.user_id, command.card_number
        )

        if existing:
            # 기존 token 반환
            return VerifyAndTokenizeCardResult(
                card_token=existing["card_token"],
                last_four=existing["last_four"],
            )

        # 카드 정보를 암호화 또는 HMAC 처리해 저장
        encrypted_data = self.card_encryptor.encrypt_card_data(
            command.card_number, command.expiry, command.cvc
        )

        # card_token 발급
        card_token = f"card-token-{uuid.uuid4().hex[:12]}"
        last_four = command.card_number[-4:]

        self.card_token_repository.save_card_token(
            user_id=command.user_id,
            card_number=command.card_number,
            card_token=card_token,
            last_four=last_four,
            encrypted_data=encrypted_data,
        )

        return VerifyAndTokenizeCardResult(
            card_token=card_token,
            last_four=last_four,
        )