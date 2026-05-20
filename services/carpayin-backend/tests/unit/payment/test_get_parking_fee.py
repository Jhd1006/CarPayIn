"""
요금 조회 / 결제 / 출차 유스케이스 단위 테스트
UC-PAY-001: 현재 주차 요금 조회와 quote 생성
"""

import pytest

from app.application.payment.get_parking_fee import (
    GetParkingFeeCommand,
    GetParkingFeeService,
)


VALID_ACCESS_TOKEN = "at_valid_token_001"
VALID_SESSION_ID = "parking-session-001"
VALID_CAR_ID = "car-001"
VALID_USER_ID = "user-001"
VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"
VALID_ENTRY_TIME = "2026-05-20T14:30:00"
VALID_AMOUNT = 5000
VALID_CURRENCY = "KRW"
FEE_QUOTE_TTL = 300  # 5분


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
    ):
        self.sessions[session_id] = {
            "session_id": session_id,
            "car_id": car_id,
            "lot_id": lot_id,
            "plate": plate,
            "entry_time": entry_time,
            "status": status,
        }

    def get_session_by_id(self, session_id: str):
        return self.sessions.get(session_id)


class FakeFeeQuoteStore:
    def __init__(self):
        self.quotes = {}

    def get_quote(self, session_id: str):
        return self.quotes.get(session_id)

    def save_quote(
        self,
        *,
        session_id: str,
        lot_id: str,
        amount: int,
        currency: str,
        entry_time: str,
        ttl_seconds: int,
    ):
        self.quotes[session_id] = {
            "session_id": session_id,
            "lot_id": lot_id,
            "amount": amount,
            "currency": currency,
            "entry_time": entry_time,
            "status": "active",
            "ttl_seconds": ttl_seconds,
        }


class FakePmsClient:
    def __init__(self):
        self.fee_requests = []
        self.should_fail = False

    def get_parking_fee(
        self, *, pms_session_id: str, lot_id: str, plate: str
    ) -> dict:
        if self.should_fail:
            raise Exception("PMS fee API failed")

        self.fee_requests.append(
            {"pms_session_id": pms_session_id, "lot_id": lot_id, "plate": plate}
        )

        return {
            "amount": VALID_AMOUNT,
            "currency": VALID_CURRENCY,
        }


@pytest.fixture
def fake_token_validator():
    return FakeTokenValidator()


@pytest.fixture
def fake_parking_session_repository():
    return FakeParkingSessionRepository()


@pytest.fixture
def fake_fee_quote_store():
    return FakeFeeQuoteStore()


@pytest.fixture
def fake_pms_client():
    return FakePmsClient()


@pytest.fixture
def get_parking_fee_service(
    fake_token_validator,
    fake_parking_session_repository,
    fake_fee_quote_store,
    fake_pms_client,
):
    return GetParkingFeeService(
        token_validator=fake_token_validator,
        parking_session_repository=fake_parking_session_repository,
        fee_quote_store=fake_fee_quote_store,
        pms_client=fake_pms_client,
    )


class TestGetParkingFee:
    """UC-PAY-001 - GET /parking/session/{session_id}/fee"""

    def test_invalid_access_token_raises_error(self, get_parking_fee_service):
        """유효하지 않은 access token이면 401을 반환한다."""
        command = GetParkingFeeCommand(
            access_token="invalid-token",
            session_id=VALID_SESSION_ID,
        )

        with pytest.raises(ValueError) as exc_info:
            get_parking_fee_service.execute(command)

        assert str(exc_info.value) == "invalid_token"

    def test_session_not_found_raises_error(
        self,
        get_parking_fee_service,
    ):
        """session이 없으면 404를 반환한다."""
        command = GetParkingFeeCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id="non-existent-session",
        )

        with pytest.raises(ValueError) as exc_info:
            get_parking_fee_service.execute(command)

        assert str(exc_info.value) == "session_not_found"

    def test_session_not_active_raises_error(
        self,
        get_parking_fee_service,
        fake_parking_session_repository,
    ):
        """session이 active가 아니면 404를 반환한다."""
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
            status="completed",
        )

        command = GetParkingFeeCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
        )

        with pytest.raises(ValueError) as exc_info:
            get_parking_fee_service.execute(command)

        assert str(exc_info.value) == "session_not_active"

    def test_session_car_id_mismatch_raises_error(
        self,
        get_parking_fee_service,
        fake_parking_session_repository,
    ):
        """session과 소유차량이 불일치하면 403을 반환한다."""
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id="other-car-id",
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
            status="active",
        )

        command = GetParkingFeeCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
        )

        with pytest.raises(ValueError) as exc_info:
            get_parking_fee_service.execute(command)

        assert str(exc_info.value) == "session_car_id_mismatch"

    def test_pms_fee_query_failure_raises_error(
        self,
        get_parking_fee_service,
        fake_parking_session_repository,
        fake_pms_client,
    ):
        """PMS fee 조회에 실패하면 500을 반환한다."""
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
            status="active",
        )
        fake_pms_client.should_fail = True

        command = GetParkingFeeCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
        )

        with pytest.raises(Exception) as exc_info:
            get_parking_fee_service.execute(command)

        assert "PMS fee API failed" in str(exc_info.value)

    def test_redis_quote_exists_does_not_call_pms(
        self,
        get_parking_fee_service,
        fake_parking_session_repository,
        fake_fee_quote_store,
        fake_pms_client,
    ):
        """Redis quote가 있으면 PMS를 호출하지 않고 반환한다."""
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
            status="active",
        )
        fake_fee_quote_store.save_quote(
            session_id=VALID_SESSION_ID,
            lot_id=VALID_LOT_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            entry_time=VALID_ENTRY_TIME,
            ttl_seconds=FEE_QUOTE_TTL,
        )

        command = GetParkingFeeCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
        )

        result = get_parking_fee_service.execute(command)

        # PMS 호출되지 않음
        assert len(fake_pms_client.fee_requests) == 0

        # 응답 확인
        assert result.session_id == VALID_SESSION_ID
        assert result.lot_id == VALID_LOT_ID
        assert result.amount == VALID_AMOUNT
        assert result.currency == VALID_CURRENCY
        assert result.status == "active"

    def test_redis_quote_not_exists_calls_pms_and_saves_quote(
        self,
        get_parking_fee_service,
        fake_parking_session_repository,
        fake_fee_quote_store,
        fake_pms_client,
    ):
        """Redis quote가 없으면 PMS를 호출하고 quote를 저장한다."""
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
            status="active",
        )

        command = GetParkingFeeCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
        )

        result = get_parking_fee_service.execute(command)

        # PMS 호출됨
        assert len(fake_pms_client.fee_requests) == 1
        assert fake_pms_client.fee_requests[0]["lot_id"] == VALID_LOT_ID
        assert fake_pms_client.fee_requests[0]["plate"] == VALID_PLATE

        # Redis에 quote 저장됨
        saved_quote = fake_fee_quote_store.get_quote(VALID_SESSION_ID)
        assert saved_quote is not None
        assert saved_quote["amount"] == VALID_AMOUNT
        assert saved_quote["currency"] == VALID_CURRENCY
        assert saved_quote["ttl_seconds"] == FEE_QUOTE_TTL

        # 응답 확인
        assert result.session_id == VALID_SESSION_ID
        assert result.lot_id == VALID_LOT_ID
        assert result.amount == VALID_AMOUNT
        assert result.currency == VALID_CURRENCY
        assert result.status == "active"