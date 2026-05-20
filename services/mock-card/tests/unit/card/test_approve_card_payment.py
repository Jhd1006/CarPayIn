"""
Mock Card 유스케이스 단위 테스트
UC-CARDCO-002: card token 결제 승인
"""

import pytest

from app.application.card.approve_card_payment import (
    ApproveCardPaymentCommand,
    ApproveCardPaymentService,
)


VALID_CARD_TOKEN = "card-token-001"
VALID_AMOUNT = 5000
VALID_CURRENCY = "KRW"
VALID_IDEMPOTENCY_KEY = "idem-key-001"


class FakeCardTokenRepository:
    def __init__(self):
        self.tokens = {}

    def add_card_token(self, card_token: str, status: str = "active"):
        self.tokens[card_token] = {
            "card_token": card_token,
            "status": status,
        }

    def get_card_token(self, card_token: str):
        return self.tokens.get(card_token)


class FakeCardTransactionRepository:
    def __init__(self):
        self.transactions = {}

    def get_by_idempotency_key(self, idempotency_key: str):
        return self.transactions.get(idempotency_key)

    def create_transaction(
        self,
        *,
        tx_id: str,
        idempotency_key: str,
        card_token: str,
        amount: int,
        currency: str,
        status: str,
        approval_no: str = None,
    ):
        if idempotency_key in self.transactions:
            return self.transactions[idempotency_key]

        self.transactions[idempotency_key] = {
            "tx_id": tx_id,
            "idempotency_key": idempotency_key,
            "card_token": card_token,
            "amount": amount,
            "currency": currency,
            "status": status,
            "approval_no": approval_no,
        }
        return self.transactions[idempotency_key]


@pytest.fixture
def fake_card_token_repository():
    return FakeCardTokenRepository()


@pytest.fixture
def fake_card_transaction_repository():
    return FakeCardTransactionRepository()


@pytest.fixture
def approve_card_payment_service(
    fake_card_token_repository,
    fake_card_transaction_repository,
):
    return ApproveCardPaymentService(
        card_token_repository=fake_card_token_repository,
        card_transaction_repository=fake_card_transaction_repository,
    )


class TestApproveCardPayment:
    """UC-CARDCO-002 - card token 결제 승인"""

    def test_active_card_token_saves_success_tx(
        self,
        approve_card_payment_service,
        fake_card_token_repository,
        fake_card_transaction_repository,
    ):
        """active card_token이면 success tx를 저장한다."""
        fake_card_token_repository.add_card_token(
            VALID_CARD_TOKEN, status="active"
        )

        command = ApproveCardPaymentCommand(
            card_token=VALID_CARD_TOKEN,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            idempotency_key=VALID_IDEMPOTENCY_KEY,
        )

        result = approve_card_payment_service.execute(command)

        # transaction 저장 확인
        tx = fake_card_transaction_repository.get_by_idempotency_key(
            VALID_IDEMPOTENCY_KEY
        )
        assert tx is not None
        assert tx["card_token"] == VALID_CARD_TOKEN
        assert tx["amount"] == VALID_AMOUNT
        assert tx["currency"] == VALID_CURRENCY
        assert tx["status"] == "success"
        assert tx["approval_no"] is not None

        # 응답 확인
        assert result.status == "success"
        assert result.approval_no is not None
        assert result.tx_id is not None

    def test_duplicate_idempotency_key_returns_existing_tx(
        self,
        approve_card_payment_service,
        fake_card_token_repository,
        fake_card_transaction_repository
    ):
        """같은 idempotency_key 재요청은 기존 tx를 반환한다."""
        fake_card_token_repository.add_card_token(
            VALID_CARD_TOKEN, status="active"
        )

        command = ApproveCardPaymentCommand(
            card_token=VALID_CARD_TOKEN,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            idempotency_key=VALID_IDEMPOTENCY_KEY,
        )

        # 첫 번째 요청
        first_result = approve_card_payment_service.execute(command)

        # 두 번째 요청
        second_result = approve_card_payment_service.execute(command)

        # 같은 결과 반환
        assert first_result.tx_id == second_result.tx_id
        assert first_result.approval_no == second_result.approval_no
        assert first_result.status == second_result.status

        # transaction이 하나만 존재
        assert len(fake_card_transaction_repository.transactions) == 1

    def test_inactive_card_token_returns_failed(
        self,
        approve_card_payment_service,
        fake_card_token_repository,
        fake_card_transaction_repository,
    ):
        """inactive card_token이면 failed를 반환한다."""
        fake_card_token_repository.add_card_token(
            VALID_CARD_TOKEN, status="inactive"
        )

        command = ApproveCardPaymentCommand(
            card_token=VALID_CARD_TOKEN,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            idempotency_key=VALID_IDEMPOTENCY_KEY,
        )

        result = approve_card_payment_service.execute(command)

        # failed transaction 저장 확인
        tx = fake_card_transaction_repository.get_by_idempotency_key(
            VALID_IDEMPOTENCY_KEY
        )
        assert tx is not None
        assert tx["status"] == "failed"
        assert tx["approval_no"] is None

        # 응답 확인
        assert result.status == "failed"
        assert result.approval_no is None