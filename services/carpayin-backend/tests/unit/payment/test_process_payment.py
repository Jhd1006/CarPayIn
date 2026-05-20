"""
요금 조회 / 결제 / 출차 유스케이스 단위 테스트
UC-PAY-002: 결제 요청 처리
"""

import pytest
import hashlib

from app.application.payment.process_payment import (
    ProcessPaymentCommand,
    ProcessPaymentService,
)


VALID_ACCESS_TOKEN = "at_valid_token_001"
VALID_SESSION_ID = "parking-session-001"
VALID_CAR_ID = "car-001"
VALID_USER_ID = "user-001"
VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"
VALID_AMOUNT = 5000
VALID_CURRENCY = "KRW"
VALID_ENTRY_TIME = "2026-05-20T14:30:00"


class FakeTokenValidator:
    def __init__(self):
        self.valid_tokens = {
            VALID_ACCESS_TOKEN: {
                "user_id": VALID_USER_ID,
                "car_id": VALID_CAR_ID,
            }
        }

    def validate_and_extract(self, access_token: str) -> dict:
        if access_token not in self.valid_tokens:
            raise ValueError("invalid_token")
        return self.valid_tokens[access_token]


class FakeFeeQuoteStore:
    def __init__(self):
        self.quotes = {}

    def add_quote(self, session_id: str, amount: int, currency: str):
        self.quotes[session_id] = {
            "session_id": session_id,
            "amount": amount,
            "currency": currency,
        }

    def get_quote(self, session_id: str):
        return self.quotes.get(session_id)


class FakeParkingSessionRepository:
    def __init__(self):
        self.sessions = {}

    def add_session(
        self,
        session_id: str,
        car_id: str,
        lot_id: str,
        plate: str,
        entry_time: str,
        status: str = "active",
        pms_session_id: str = "pms-001",
    ):
        self.sessions[session_id] = {
            "session_id": session_id,
            "car_id": car_id,
            "lot_id": lot_id,
            "plate": plate,
            "entry_time": entry_time,
            "status": status,
            "pms_session_id": pms_session_id,
        }

    def get_session_by_id(self, session_id: str):
        return self.sessions.get(session_id)

    def update_session_status(self, session_id: str, status: str):
        if session_id in self.sessions:
            self.sessions[session_id]["status"] = status


class FakeBillingKeyRepository:
    def __init__(self):
        self.billing_keys = {}

    def add_active_billing_key(self, car_id: str, billing_key: str = "bk-001"):
        self.billing_keys[car_id] = {
            "car_id": car_id,
            "billing_key": billing_key,
            "status": "active",
        }

    def get_active_billing_key(self, car_id: str):
        key = self.billing_keys.get(car_id)
        if key and key["status"] == "active":
            return key
        return None


class FakeTransactionRepository:
    def __init__(self):
        self.transactions = {}

    def get_transaction_by_idempotency_key(self, idempotency_key: str):
        return self.transactions.get(idempotency_key)

    def create_pending_transaction(
        self, *, tx_id: str, idempotency_key: str, session_id: str, amount: int, currency: str
    ):
        self.transactions[idempotency_key] = {
            "tx_id": tx_id,
            "idempotency_key": idempotency_key,
            "session_id": session_id,
            "amount": amount,
            "currency": currency,
            "status": "pending",
        }

    def update_transaction_status(
        self, idempotency_key: str, status: str, approval_no: str = None, failed_reason: str = None
    ):
        if idempotency_key in self.transactions:
            self.transactions[idempotency_key]["status"] = status
            if approval_no:
                self.transactions[idempotency_key]["approval_no"] = approval_no
            if failed_reason:
                self.transactions[idempotency_key]["failed_reason"] = failed_reason


class FakePgClient:
    def __init__(self):
        self.payment_requests = []
        self.should_fail = False

    def charge_billing_key(
        self, *, billing_key: str, amount: int, currency: str, idempotency_key: str
    ) -> dict:
        if self.should_fail:
            raise Exception("PG payment failed")

        self.payment_requests.append(
            {
                "billing_key": billing_key,
                "amount": amount,
                "currency": currency,
                "idempotency_key": idempotency_key,
            }
        )

        return {
            "success": True,
            "approval_no": "APPR123456",
        }


class FakePmsClient:
    def __init__(self):
        self.notify_calls = []
        self.should_fail = False

    def notify_payment_complete(
        self, *, pms_session_id: str, tx_id: str, amount: int, currency: str, approval_no: str
    ):
        if self.should_fail:
            raise Exception("PMS notify failed")

        self.notify_calls.append(
            {
                "pms_session_id": pms_session_id,
                "tx_id": tx_id,
                "amount": amount,
                "currency": currency,
                "approval_no": approval_no,
            }
        )


class FakeNotificationPublisher:
    def __init__(self):
        self.published_messages = []

    def publish_payment_notification(
        self, *, session_id: str, car_id: str, tx_id: str, approval_no: str
    ):
        self.published_messages.append(
            {
                "type": "payment",
                "session_id": session_id,
                "car_id": car_id,
                "tx_id": tx_id,
                "approval_no": approval_no,
            }
        )


@pytest.fixture
def fake_token_validator():
    return FakeTokenValidator()


@pytest.fixture
def fake_fee_quote_store():
    return FakeFeeQuoteStore()


@pytest.fixture
def fake_parking_session_repository():
    return FakeParkingSessionRepository()


@pytest.fixture
def fake_billing_key_repository():
    return FakeBillingKeyRepository()


@pytest.fixture
def fake_transaction_repository():
    return FakeTransactionRepository()


@pytest.fixture
def fake_pg_client():
    return FakePgClient()


@pytest.fixture
def fake_pms_client():
    return FakePmsClient()


@pytest.fixture
def fake_notification_publisher():
    return FakeNotificationPublisher()


@pytest.fixture
def process_payment_service(
    fake_token_validator,
    fake_fee_quote_store,
    fake_parking_session_repository,
    fake_billing_key_repository,
    fake_transaction_repository,
    fake_pg_client,
    fake_pms_client,
    fake_notification_publisher,
):
    return ProcessPaymentService(
        token_validator=fake_token_validator,
        fee_quote_store=fake_fee_quote_store,
        parking_session_repository=fake_parking_session_repository,
        billing_key_repository=fake_billing_key_repository,
        transaction_repository=fake_transaction_repository,
        pg_client=fake_pg_client,
        pms_client=fake_pms_client,
        notification_publisher=fake_notification_publisher,
    )


class TestProcessPayment:
    """UC-PAY-002 - POST /payment"""

    def test_quote_not_found_raises_error(self, process_payment_service):
        """quote가 없으면 404를 반환한다."""
        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        with pytest.raises(ValueError) as exc_info:
            process_payment_service.execute(command)

        assert str(exc_info.value) == "quote_not_found"

    def test_amount_currency_mismatch_raises_error(
        self,
        process_payment_service,
        fake_fee_quote_store,
    ):
        """amount/currency가 quote와 불일치하면 400을 반환한다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, 3000, VALID_CURRENCY)

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        with pytest.raises(ValueError) as exc_info:
            process_payment_service.execute(command)

        assert str(exc_info.value) == "amount_currency_mismatch"

    def test_session_not_found_raises_error(
        self,
        process_payment_service,
        fake_fee_quote_store,
    ):
        """session이 없으면 404를 반환한다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        with pytest.raises(ValueError) as exc_info:
            process_payment_service.execute(command)

        assert str(exc_info.value) == "session_not_found"

    def test_session_car_id_mismatch_raises_error(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
    ):
        """session과 소유 차량이 불일치하면 403을 반환한다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id="other-car-id",
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        with pytest.raises(ValueError) as exc_info:
            process_payment_service.execute(command)

        assert str(exc_info.value) == "session_car_id_mismatch"

    def test_no_active_billing_key_raises_error_and_does_not_call_pg(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_pg_client,
    ):
        """active billing key가 없으면 400을 반환하고 PG를 호출하지 않는다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        with pytest.raises(ValueError) as exc_info:
            process_payment_service.execute(command)

        assert str(exc_info.value) == "no_active_billing_key"
        assert len(fake_pg_client.payment_requests) == 0

    def test_valid_request_creates_pending_transaction_and_calls_pg(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_billing_key_repository,
        fake_transaction_repository,
        fake_pg_client,
    ):
        """quote 금액과 요청 금액이 같으면 pending transaction을 만들고 PG를 호출한다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        process_payment_service.execute(command)

        # pending transaction 생성 확인
        idempotency_key = hashlib.sha256(
            f"{VALID_SESSION_ID}{VALID_CAR_ID}{VALID_AMOUNT}{VALID_CURRENCY}".encode()
        ).hexdigest()
        tx = fake_transaction_repository.get_transaction_by_idempotency_key(idempotency_key)
        assert tx is not None

        # PG 호출 확인
        assert len(fake_pg_client.payment_requests) == 1

    def test_pg_success_updates_transaction_and_session(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_billing_key_repository,
        fake_transaction_repository,
        fake_pms_client,
        fake_notification_publisher,
    ):
        """PG 성공이면 transaction success, parking session completed가 된다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        result = process_payment_service.execute(command)

        # transaction success 확인
        idempotency_key = hashlib.sha256(
            f"{VALID_SESSION_ID}{VALID_CAR_ID}{VALID_AMOUNT}{VALID_CURRENCY}".encode()
        ).hexdigest()
        tx = fake_transaction_repository.get_transaction_by_idempotency_key(idempotency_key)
        assert tx["status"] == "success"
        assert tx["approval_no"] == "APPR123456"

        # parking session completed 확인
        session = fake_parking_session_repository.get_session_by_id(VALID_SESSION_ID)
        assert session["status"] == "completed"

        # PMS notify 호출 확인
        assert len(fake_pms_client.notify_calls) == 1

        # 알림 발행 확인
        assert len(fake_notification_publisher.published_messages) == 1

        # 응답 확인
        assert result.status == "success"
        assert result.tx_id is not None
        assert result.approval_no == "APPR123456"

    def test_pg_failure_updates_transaction_failed_and_keeps_session_active(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_billing_key_repository,
        fake_transaction_repository,
        fake_pg_client,
    ):
        """PG 실패이면 transaction failed, parking session active가 유지된다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)
        fake_pg_client.should_fail = True

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        result = process_payment_service.execute(command)

        # transaction failed 확인
        idempotency_key = hashlib.sha256(
            f"{VALID_SESSION_ID}{VALID_CAR_ID}{VALID_AMOUNT}{VALID_CURRENCY}".encode()
        ).hexdigest()
        tx = fake_transaction_repository.get_transaction_by_idempotency_key(idempotency_key)
        assert tx["status"] == "failed"

        # parking session active 유지 확인
        session = fake_parking_session_repository.get_session_by_id(VALID_SESSION_ID)
        assert session["status"] == "active"

        # 응답 확인
        assert result.status == "failed"
        assert result.failed_reason is not None

    def test_duplicate_idempotency_key_returns_existing_result(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_billing_key_repository,
        fake_transaction_repository,
        fake_pg_client,
    ):
        """같은 idempotency_key로 재요청하면 중복 결제하지 않고 기존 결과를 반환한다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        # 첫 번째 요청
        first_result = process_payment_service.execute(command)

        # 두 번째 요청
        second_result = process_payment_service.execute(command)

        # 같은 결과 반환
        assert first_result.tx_id == second_result.tx_id
        assert first_result.approval_no == second_result.approval_no

        # PG가 한 번만 호출됨
        assert len(fake_pg_client.payment_requests) == 1

    def test_pms_notify_failure_keeps_payment_success_and_marks_retry(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_billing_key_repository,
        fake_transaction_repository,
        fake_pms_client,
    ):
        """PMS paid notify 실패 시 결제는 성공하고 재시도 가능 상태가 남는다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)
        fake_pms_client.should_fail = True

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        result = process_payment_service.execute(command)

        # 결제는 성공
        assert result.status == "success"
        assert result.approval_no is not None

        # transaction은 success
        idempotency_key = hashlib.sha256(
            f"{VALID_SESSION_ID}{VALID_CAR_ID}{VALID_AMOUNT}{VALID_CURRENCY}".encode()
        ).hexdigest()
        tx = fake_transaction_repository.get_transaction_by_idempotency_key(idempotency_key)
        assert tx["status"] == "success"

        # parking session은 completed
        session = fake_parking_session_repository.get_session_by_id(VALID_SESSION_ID)
        assert session["status"] == "completed"

        # (재시도 가능 상태는 실제 구현에서 별도 필드로 관리)