"""
Mock Card 유스케이스 단위 테스트
UC-CARDCO-001: 카드 검증과 card token 발급
"""

import pytest
from datetime import datetime

from app.application.card.verify_and_tokenize_card import (
    VerifyAndTokenizeCardCommand,
    VerifyAndTokenizeCardService,
)


VALID_CARD_NUMBER = "1234567890123456"
VALID_EXPIRY = "12/28"
VALID_CVC = "123"
EXPIRED_EXPIRY = "12/20"
VALID_USER_ID = "user-001"


class FakeCardValidator:
    def validate_card(self, card_number: str, expiry: str, cvc: str) -> bool:
        # 카드번호 길이 확인
        if len(card_number) != 16:
            return False

        # 만료일 확인
        try:
            month, year = expiry.split("/")
            expiry_date = datetime(2000 + int(year), int(month), 1)
            if expiry_date < datetime.now():
                return False
        except (ValueError, IndexError):
            return False

        # CVC 길이 확인
        if len(cvc) != 3:
            return False

        return True


class FakeCardTokenRepository:
    def __init__(self):
        self.users = {}
        self.tokens = {}

    def upsert_user(self, *, user_id: str, name: str):
        self.users[user_id] = {"user_id": user_id, "name": name}

    def get_by_user_and_encrypted_card(self, *, user_id: str, encrypted_card_num: str):
        key = f"{user_id}:{encrypted_card_num}"
        return self.tokens.get(key)

    def save_card_with_token(
        self,
        *,
        user_id: str,
        encrypted_card_num: str,
        cvc_hmac: str,
        exp_month: int,
        exp_year: int,
        card_token: str,
    ):
        key = f"{user_id}:{encrypted_card_num}"
        if key in self.tokens:
            return self.tokens[key]

        self.tokens[key] = {
            "user_id": user_id,
            "encrypted_card_num": encrypted_card_num,
            "cvc_hmac": cvc_hmac,
            "exp_month": exp_month,
            "exp_year": exp_year,
            "card_token": card_token,
            "status": "active",
        }
        return self.tokens[key]


class FakeCardEncryptor:
    def encrypt_card_number(self, card_number: str) -> str:
        return f"encrypted_{card_number}"

    def hash_cvc(self, cvc: str) -> str:
        return f"hmac_{cvc}"


@pytest.fixture
def fake_card_validator():
    return FakeCardValidator()


@pytest.fixture
def fake_card_token_repository():
    return FakeCardTokenRepository()


@pytest.fixture
def fake_card_encryptor():
    return FakeCardEncryptor()


@pytest.fixture
def verify_and_tokenize_card_service(
    fake_card_validator,
    fake_card_token_repository,
    fake_card_encryptor,
):
    return VerifyAndTokenizeCardService(
        card_validator=fake_card_validator,
        card_token_repository=fake_card_token_repository,
        card_encryptor=fake_card_encryptor,
    )


class TestVerifyAndTokenizeCard:
    """UC-CARDCO-001 - 카드 검증과 card token 발급"""

    def test_valid_card_returns_card_token_and_last_four(
        self,
        verify_and_tokenize_card_service,
        fake_card_token_repository,
    ):
        """유효한 카드면 card_token과 last_four를 반환한다."""
        command = VerifyAndTokenizeCardCommand(
            user_id=VALID_USER_ID,
            card_number=VALID_CARD_NUMBER,
            expiry=VALID_EXPIRY,
            cvc=VALID_CVC,
        )

        result = verify_and_tokenize_card_service.execute(command)

        # card_token 발급 확인
        assert result.card_token is not None
        assert result.last_four == VALID_CARD_NUMBER[-4:]

        # 저장 확인
        saved = fake_card_token_repository.get_by_user_and_encrypted_card(
            user_id=VALID_USER_ID,
            encrypted_card_num=f"encrypted_{VALID_CARD_NUMBER}",
        )
        assert saved is not None
        assert saved["card_token"] == result.card_token
        assert saved["status"] == "active"
        assert saved["encrypted_card_num"] == f"encrypted_{VALID_CARD_NUMBER}"
        assert saved["cvc_hmac"] == f"hmac_{VALID_CVC}"

    def test_expired_card_fails(
        self,
        verify_and_tokenize_card_service,
    ):
        """만료 카드면 실패한다."""
        command = VerifyAndTokenizeCardCommand(
            user_id=VALID_USER_ID,
            card_number=VALID_CARD_NUMBER,
            expiry=EXPIRED_EXPIRY,
            cvc=VALID_CVC,
        )

        with pytest.raises(ValueError) as exc_info:
            verify_and_tokenize_card_service.execute(command)

        assert str(exc_info.value) == "invalid_card"

    def test_duplicate_user_and_card_returns_existing_token(
        self,
        verify_and_tokenize_card_service,
        fake_card_token_repository,
    ):
        """같은 사용자와 카드의 중복 등록은 기존 카드 또는 token 정책에 따라 처리된다."""
        command = VerifyAndTokenizeCardCommand(
            user_id=VALID_USER_ID,
            card_number=VALID_CARD_NUMBER,
            expiry=VALID_EXPIRY,
            cvc=VALID_CVC,
        )

        # 첫 번째 요청
        first_result = verify_and_tokenize_card_service.execute(command)
        first_token = first_result.card_token

        # 두 번째 요청
        second_result = verify_and_tokenize_card_service.execute(command)

        # 같은 token 반환
        assert second_result.card_token == first_token
        assert second_result.last_four == VALID_CARD_NUMBER[-4:]

        # 토큰이 하나만 존재
        assert len(fake_card_token_repository.tokens) == 1
