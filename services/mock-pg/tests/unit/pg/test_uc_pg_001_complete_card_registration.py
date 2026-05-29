"""
Mock PG 유스케이스 단위 테스트
UC-PG-001: 카드 등록 WebView 완료와 billing key 발급
"""

import pytest

from app.application.pg.complete_card_registration import (
    CompleteCardRegistrationCommand,
    CompleteCardRegistrationService,
)


VALID_ORDER_ID = "order-001"
VALID_CARD_NUMBER = "1234567890123456"
VALID_EXPIRY = "12/28"
VALID_CVC = "123"
VALID_CARD_TOKEN = "card-token-001"
VALID_BILLING_KEY = "bk-001"


class FakeMockCardClient:
    def __init__(self):
        self.verify_calls = []
        self.should_fail = False

    def verify_and_tokenize_card(
        self, *, user_id: str, card_number: str, expiry: str, cvc: str
    ) -> dict:
        if self.should_fail:
            raise Exception("Card verification failed")

        self.verify_calls.append(
            {
                "user_id": user_id,
                "card_number": card_number,
                "expiry": expiry,
                "cvc": cvc,
            }
        )

        return {
            "card_token": VALID_CARD_TOKEN,
            "last_four": card_number[-4:],
        }


class FakeBillingKeyRepository:
    def __init__(self):
        self.billing_keys = {}

    def get_by_order_id(self, order_id: str):
        return self.billing_keys.get(order_id)

    def save_billing_key(
        self, *, order_id: str, billing_key: str, card_token: str, last_four: str
    ):
        if order_id in self.billing_keys:
            return self.billing_keys[order_id]

        self.billing_keys[order_id] = {
            "order_id": order_id,
            "billing_key": billing_key,
            "card_token": card_token,
            "last_four": last_four,
            "status": "active",
        }
        return self.billing_keys[order_id]


class FakeCarPayInWebhookClient:
    def __init__(self):
        self.webhook_calls = []

    def send_card_registration_webhook(
        self, *, order_id: str, billing_key: str, last_four: str
    ):
        self.webhook_calls.append(
            {
                "order_id": order_id,
                "billing_key": billing_key,
                "last_four": last_four,
            }
        )


@pytest.fixture
def fake_mock_card_client():
    return FakeMockCardClient()


@pytest.fixture
def fake_billing_key_repository():
    return FakeBillingKeyRepository()


@pytest.fixture
def fake_carpayin_webhook_client():
    return FakeCarPayInWebhookClient()


@pytest.fixture
def complete_card_registration_service(
    fake_mock_card_client,
    fake_billing_key_repository,
    fake_carpayin_webhook_client,
):
    return CompleteCardRegistrationService(
        mock_card_client=fake_mock_card_client,
        billing_key_repository=fake_billing_key_repository,
        carpayin_webhook_client=fake_carpayin_webhook_client,
    )


class TestCompleteCardRegistration:
    """UC-PG-001 - 카드 등록 WebView 완료와 billing key 발급"""

    def test_card_verification_success_saves_billing_key(
        self,
        complete_card_registration_service,
        fake_mock_card_client,
        fake_billing_key_repository,
        fake_carpayin_webhook_client,
    ):
        """카드 검증 성공이면 billing_key를 저장한다."""
        command = CompleteCardRegistrationCommand(
            order_id=VALID_ORDER_ID,
            card_number=VALID_CARD_NUMBER,
            expiry=VALID_EXPIRY,
            cvc=VALID_CVC,
        )

        result = complete_card_registration_service.execute(command)

        # billing_key 저장 확인
        saved = fake_billing_key_repository.get_by_order_id(VALID_ORDER_ID)
        assert saved is not None
        assert saved["order_id"] == VALID_ORDER_ID
        assert saved["card_token"] == VALID_CARD_TOKEN
        assert saved["last_four"] == VALID_CARD_NUMBER[-4:]
        assert saved["status"] == "active"
        assert fake_mock_card_client.verify_calls[0]["user_id"] == VALID_ORDER_ID

        # 웹훅 전송 확인
        assert len(fake_carpayin_webhook_client.webhook_calls) == 1
        webhook = fake_carpayin_webhook_client.webhook_calls[0]
        assert webhook["order_id"] == VALID_ORDER_ID
        assert webhook["billing_key"] == saved["billing_key"]
        assert webhook["last_four"] == VALID_CARD_NUMBER[-4:]

        # 응답 확인
        assert result.status == "success"
        assert result.billing_key is not None

    def test_duplicate_order_id_does_not_create_duplicate_billing_key(
        self,
        complete_card_registration_service,
        fake_billing_key_repository,
        fake_carpayin_webhook_client,
    ):
        """같은 order_id는 billing_key를 중복 생성하지 않는다."""
        command = CompleteCardRegistrationCommand(
            order_id=VALID_ORDER_ID,
            card_number=VALID_CARD_NUMBER,
            expiry=VALID_EXPIRY,
            cvc=VALID_CVC,
        )

        # 첫 번째 요청
        first_result = complete_card_registration_service.execute(command)
        first_billing_key = first_result.billing_key

        # 두 번째 요청
        second_result = complete_card_registration_service.execute(command)

        # 같은 billing_key 반환
        assert second_result.billing_key == first_billing_key

        # billing_key가 하나만 존재
        assert len(fake_billing_key_repository.billing_keys) == 1

        assert len(fake_carpayin_webhook_client.webhook_calls) == 2

    def test_card_verification_failure_does_not_send_webhook(
        self,
        complete_card_registration_service,
        fake_mock_card_client,
        fake_carpayin_webhook_client,
    ):
        """카드 검증 실패면 webhook 성공을 보내지 않는다."""
        fake_mock_card_client.should_fail = True

        command = CompleteCardRegistrationCommand(
            order_id=VALID_ORDER_ID,
            card_number=VALID_CARD_NUMBER,
            expiry=VALID_EXPIRY,
            cvc=VALID_CVC,
        )

        result = complete_card_registration_service.execute(command)

        # 실패 응답
        assert result.status == "failed"
        assert result.billing_key is None

        # 웹훅 전송되지 않음
        assert len(fake_carpayin_webhook_client.webhook_calls) == 0
