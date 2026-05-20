"""
Mock PG 유스케이스 단위 테스트
UC-PG-002: billing key 결제 승인
"""

import pytest

from app.application.pg.charge_billing_key import (
    ChargeBillingKeyCommand,
    ChargeBillingKeyService,
)


VALID_BILLING_KEY = "bk-001"
VALID_CARD_TOKEN = "card-token-001"
VALID_AMOUNT = 5000
VALID_CURRENCY = "KRW"
VALID_IDEMPOTENCY_KEY = "idem-key-001"
VALID_APPROVAL_NO = "APPR123456"


class FakeBillingKeyRepository:
    def __init__(self):
        self.billing_keys = {}

    def add_billing_key(self, billing_key: str, card_token: str, status: str = "active"):
        self.billing_keys[billing_key] = {
            "billing_key": billing_key,
            "card_token": card_token,
            "status": status,
        }

    def get_billing_key(self, billing_key: str):
        return self.billing_keys.get(billing_key)


class FakeTransactionRepository:
    def __init__(self):
        self.transactions = {}

    def get_by_idempotency_key(self, idempotency_key: str):
        return self.transactions.get(idempotency_key)

    def create_transaction(
        self,
        *,
        tx_id: str,
        idempotency_key: str,
        billing_key: str,
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
            "billing_key": billing_key,
            "amount": amount,
            "currency": currency,
            "status": status,
            "approval_no": approval_no,
        }
        return self.transactions[idempotency_key]

    def update_transaction_status(
        self, idempotency_key: str, status: str, approval_no: str = None
    ):
        if idempotency_key in self.transactions:
            self.transactions[idempotency_key]["status"] = status
            if approval_no:
                self.transactions[idempotency_key]["approval_no"] = approval_no


class FakeMockCardClient:
    def __init__(self):
        self.approval_calls = []
        self.should_fail = False

    def approve_payment(
        self, *, card_token: str, amount: int, currency: str, idempotency_key: str
    ) -> dict:
        if self.should_fail:
            raise Exception("Card approval failed")

        self.approval_calls.append(
            {
                "card_token": card_token,
                "amount": amount,
                "currency": currency,
                "idempotency_key": idempotency_key,
            }
        )

        return {
            "approval_no": VALID_APPROVAL_NO,
        }


@pytest.fixture
def fake_billing_key_repository():
    return FakeBillingKeyRepository()


@pytest.fixture
def fake_transaction_repository():
    return FakeTransactionRepository()


@pytest.fixture
def fake_mock_card_client():
    return FakeMockCardClient()


@pytest.fixture
def charge_billing_key_service(
    fake_billing_key_repository,
    fake_transaction_repository,
    fake_mock_card_client,
):
    return ChargeBillingKeyService(
        billing_key_repository=fake_billing_key_repository,
        transaction_repository=fake_transaction_repository,
        mock_card_client=fake_mock_card_client,
    )


class TestChargeBillingKey:
    """UC-PG-002 - POST /payments/billing"""

    def test_active_billing_key_approves_and_returns_success(
        self,
        charge_billing_key_service,
        fake_billing_key_repository,
        fake_transaction_repository,
        fake_mock_card_client,
    ):
        """active billing_key면 카드 승인 후 success를 반환한다."""
        fake_billing_key_repository.add_billing_key(
            VALID_BILLING_KEY, VALID_CARD_TOKEN, status="active"
        )

        command = ChargeBillingKeyCommand(
            billing_key=VALID_BILLING_KEY,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            idempotency_key=VALID_IDEMPOTENCY_KEY,
        )

        result = charge_billing_key_service.execute(command)

        # Mock Card 승인 호출 확인
        assert len(fake_mock_card_client.approval_calls) == 1
        approval_call = fake_mock_card_client.approval_calls[0]
        assert approval_call["card_token"] == VALID_CARD_TOKEN
        assert approval_call["amount"] == VALID_AMOUNT
        assert approval_call["currency"] == VALID_CURRENCY

        # transaction success 확인
        tx = fake_transaction_repository.get_by_idempotency_key(
            VALID_IDEMPOTENCY_KEY
        )
        assert tx is not None
        assert tx["status"] == "success"
        assert tx["approval_no"] == VALID_APPROVAL_NO

        # 응답 확인
        assert result.status == "success"
        assert result.approval_no == VALID_APPROVAL_NO

    def test_duplicate_idempotency_key_returns_existing_result(
        self,
        charge_billing_key_service,
        fake_billing_key_repository,
        fake_mock_card_client,
    ):
        """같은 idempotency_key 재요청은 기존 결과를 반환한다."""
        fake_billing_key_repository.add_billing_key(
            VALID_BILLING_KEY, VALID_CARD_TOKEN, status="active"
        )

        command = ChargeBillingKeyCommand(
            billing_key=VALID_BILLING_KEY,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            idempotency_key=VALID_IDEMPOTENCY_KEY,
        )

        # 첫 번째 요청
        first_result = charge_billing_key_service.execute(command)

        # 두 번째 요청
        second_result = charge_billing_key_service.execute(command)

        # 같은 결과 반환
        assert first_result.approval_no == second_result.approval_no
        assert first_result.status == second_result.status

        # Mock Card는 한 번만 호출됨
        assert len(fake_mock_card_client.approval_calls) == 1

    def test_inactive_billing_key_returns_failed(
        self,
        charge_billing_key_service,
        fake_billing_key_repository,
        fake_mock_card_client,
    ):
        """inactive billing_key면 failed를 반환한다."""
        fake_billing_key_repository.add_billing_key(
            VALID_BILLING_KEY, VALID_CARD_TOKEN, status="inactive"
        )

        command = ChargeBillingKeyCommand(
            billing_key=VALID_BILLING_KEY,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            idempotency_key=VALID_IDEMPOTENCY_KEY,
        )

        result = charge_billing_key_service.execute(command)

        # Mock Card 호출되지 않음
        assert len(fake_mock_card_client.approval_calls) == 0

        # 실패 응답
        assert result.status == "failed"
        assert result.approval_no is None