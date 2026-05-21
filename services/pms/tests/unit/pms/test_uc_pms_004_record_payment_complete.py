"""
Mock PMS 유스케이스 단위 테스트
UC-PMS-004: 결제 완료 기록
"""

import pytest

from app.application.pms.record_payment_complete import (
    RecordPaymentCompleteCommand,
    RecordPaymentCompleteService,
)


VALID_PMS_SESSION_ID = "pms-sess-001"
VALID_CARPAY_PARKING_SESSION_ID = "parking-session-001"
VALID_CARPAY_TX_ID = "tx-123456"
VALID_AMOUNT = 5000
VALID_CURRENCY = "KRW"
VALID_APPROVAL_NO = "APPR123456"
VALID_IDEMPOTENCY_KEY = "idem-key-001"


class FakePaymentRequestRepository:
    def __init__(self):
        self.payment_requests = {}

    def get_by_idempotency_key(self, idempotency_key: str):
        return self.payment_requests.get(idempotency_key)

    def save_payment_request(
        self,
        *,
        idempotency_key: str,
        pms_session_id: str,
        carpay_session_id: str,
        tx_id: str,
        amount: int,
        currency: str,
        approval_no: str,
    ):
        if idempotency_key in self.payment_requests:
            return self.payment_requests[idempotency_key]

        self.payment_requests[idempotency_key] = {
            "idempotency_key": idempotency_key,
            "pms_session_id": pms_session_id,
            "carpay_session_id": carpay_session_id,
            "tx_id": tx_id,
            "amount": amount,
            "currency": currency,
            "approval_no": approval_no,
            "status": "success",
        }
        return self.payment_requests[idempotency_key]


@pytest.fixture
def fake_payment_request_repository():
    return FakePaymentRequestRepository()


@pytest.fixture
def record_payment_complete_service(fake_payment_request_repository):
    return RecordPaymentCompleteService(
        payment_request_repository=fake_payment_request_repository,
    )


class TestRecordPaymentComplete:
    """UC-PMS-004 - POST /pms/payment/complete"""

    def test_payment_complete_request_is_saved_as_success(
        self,
        record_payment_complete_service,
        fake_payment_request_repository,
    ):
        """결제 완료 요청을 success로 저장한다."""
        command = RecordPaymentCompleteCommand(
            pms_session_id=VALID_PMS_SESSION_ID,
            carpay_session_id=VALID_CARPAY_PARKING_SESSION_ID,
            tx_id=VALID_CARPAY_TX_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            approval_no=VALID_APPROVAL_NO,
            idempotency_key=VALID_IDEMPOTENCY_KEY,
        )

        result = record_payment_complete_service.execute(command)

        # 저장 확인
        saved = fake_payment_request_repository.get_by_idempotency_key(
            VALID_IDEMPOTENCY_KEY
        )
        assert saved is not None
        assert saved["pms_session_id"] == VALID_PMS_SESSION_ID
        assert saved["carpay_session_id"] == VALID_CARPAY_SESSION_ID
        assert saved["tx_id"] == VALID_TX_ID
        assert saved["amount"] == VALID_AMOUNT
        assert saved["currency"] == VALID_CURRENCY
        assert saved["approval_no"] == VALID_APPROVAL_NO
        assert saved["status"] == "success"

        # 응답 확인
        assert result.status == "success"

    def test_duplicate_idempotency_key_returns_existing_result(
        self,
        record_payment_complete_service,
        fake_payment_request_repository,
    ):
        """같은 idempotency_key 재요청은 기존 결과를 반환한다."""
        command = RecordPaymentCompleteCommand(
            pms_session_id=VALID_PMS_SESSION_ID,
            carpay_session_id=VALID_CARPAY_SESSION_ID,
            tx_id=VALID_TX_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            approval_no=VALID_APPROVAL_NO,
            idempotency_key=VALID_IDEMPOTENCY_KEY,
        )

        # 첫 번째 요청
        first_result = record_payment_complete_service.execute(command)

        # 두 번째 요청
        second_result = record_payment_complete_service.execute(command)

        # 같은 결과 반환
        assert first_result.status == second_result.status

        # 중복 저장되지 않음 (1개만 존재)
        all_requests = fake_payment_request_repository.payment_requests
        assert len(all_requests) == 1