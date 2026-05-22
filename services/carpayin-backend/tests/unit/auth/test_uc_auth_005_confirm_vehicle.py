"""
차량 확정 / 앱 토큰 발급 유스케이스 단위 테스트
UC-AUTH-005: 차량 선택 확정과 앱 토큰 발급
"""

import pytest

from app.application.auth.confirm_vehicle import (
    ConfirmVehicleCommand,
    ConfirmVehicleService,
)


VALID_TEMP_ACCESS_TOKEN = "temp-access-001"
EXPIRED_TEMP_ACCESS_TOKEN = "temp-access-expired"
VALID_SESSION_ID = "sess-001"
VALID_USER_ID = "hyundai-user-001"
VALID_USER_NAME = "홍길동"
VALID_CAR_ID = "hyundai-car-001"
OTHER_CAR_ID = "hyundai-car-999"
VALID_VIN_HASH = "vin-hash-001"
OTHER_VIN_HASH = "vin-hash-other"
VALID_APP_ACCESS_TOKEN = "app-access-001"
VALID_APP_REFRESH_TOKEN = "app-refresh-001"
VALID_REFRESH_TOKEN_HASH = "refresh-token-hash-001"
ERROR_TEMP_TOKEN_EXPIRED = "temp_token_expired"
ERROR_CAR_ID_NOT_IN_LIST = "car_id_not_in_list"
ERROR_VIN_HASH_MISMATCH = "vin_hash_mismatch"
ERROR_QR_SESSION_EXPIRED = "qr_session_expired"
VALID_CARS = [
    {
        "car_id": VALID_CAR_ID,
        "car_sellname": "아이오닉 6",
        "plate": "12가 3456",
    },
    {
        "car_id": "hyundai-car-002",
        "car_sellname": "쏘나타",
        "plate": "34나 7890",
    },
]


class FakeTempAccessTokenValidator:
    def __init__(self):
        self.valid_tokens = {
            VALID_TEMP_ACCESS_TOKEN: {
                "user_id": VALID_USER_ID,
                "session_id": VALID_SESSION_ID,
            }
        }

    def validate_and_extract(self, temp_access_token: str):
        if temp_access_token == EXPIRED_TEMP_ACCESS_TOKEN:
            raise ValueError(ERROR_TEMP_TOKEN_EXPIRED)

        return self.valid_tokens[temp_access_token]


class FakeHyundaiOAuthResultStore:
    def __init__(self):
        self.results = {}

    def add_result(self, session_id: str):
        self.results[session_id] = {
            "session_id": session_id,
            "user_id": VALID_USER_ID,
            "name": VALID_USER_NAME,
            "cars": VALID_CARS,
        }

    def get_result(self, session_id: str):
        return self.results.get(session_id)


class FakeAppLoginResultStore:
    def __init__(self):
        self.results = {}
        self.used_sessions = []

    def add_complete_result(self, session_id: str):
        self.results[session_id] = {
            "session_id": session_id,
            "status": "complete",
            "user_id": VALID_USER_ID,
            "name": VALID_USER_NAME,
            "cars": VALID_CARS,
        }

    def get_result(self, session_id: str):
        return self.results.get(session_id)

    def mark_used(self, session_id: str):
        self.used_sessions.append(session_id)


class FakeQrSessionStore:
    def __init__(self):
        self.sessions = {}

    def add_session(self, *, session_id: str, vin_hash: str, status: str):
        self.sessions[session_id] = {
            "session_id": session_id,
            "vin_hash": vin_hash,
            "status": status,
        }

    def get_session(self, session_id: str):
        return self.sessions.get(session_id)


class FakeVehicleRepository:
    def __init__(self):
        self.saved_vehicles = []

    def upsert_vehicle(self, *, user_id: str, car: dict):
        self.saved_vehicles.append(
            {
                "user_id": user_id,
                "car": car,
            }
        )


class FakeAppRefreshTokenRepository:
    def __init__(self):
        self.saved_token_hashes = []

    def save_token_hash(self, *, token_hash: str, user_id: str, car_id: str):
        self.saved_token_hashes.append(
            {
                "token_hash": token_hash,
                "user_id": user_id,
                "car_id": car_id,
            }
        )


class FakeAppTokenIssuer:
    def __init__(self):
        self.issue_calls = []

    def issue(self, *, user_id: str, car_id: str):
        self.issue_calls.append(
            {
                "user_id": user_id,
                "car_id": car_id,
            }
        )
        return {
            "access_token": VALID_APP_ACCESS_TOKEN,
            "refresh_token": VALID_APP_REFRESH_TOKEN,
        }


class FakeRefreshTokenHasher:
    def __init__(self):
        self.hash_calls = []

    def hash(self, refresh_token: str):
        self.hash_calls.append(refresh_token)
        return VALID_REFRESH_TOKEN_HASH


@pytest.fixture
def fake_temp_access_token_validator():
    return FakeTempAccessTokenValidator()


@pytest.fixture
def fake_hyundai_oauth_result_store():
    return FakeHyundaiOAuthResultStore()


@pytest.fixture
def fake_app_login_result_store():
    return FakeAppLoginResultStore()


@pytest.fixture
def fake_qr_session_store():
    return FakeQrSessionStore()


@pytest.fixture
def fake_vehicle_repository():
    return FakeVehicleRepository()


@pytest.fixture
def fake_app_refresh_token_repository():
    return FakeAppRefreshTokenRepository()


@pytest.fixture
def fake_app_token_issuer():
    return FakeAppTokenIssuer()


@pytest.fixture
def fake_refresh_token_hasher():
    return FakeRefreshTokenHasher()


@pytest.fixture
def confirm_vehicle_service(
    fake_temp_access_token_validator,
    fake_hyundai_oauth_result_store,
    fake_app_login_result_store,
    fake_qr_session_store,
    fake_vehicle_repository,
    fake_app_refresh_token_repository,
    fake_app_token_issuer,
    fake_refresh_token_hasher,
):
    return ConfirmVehicleService(
        temp_access_token_validator=fake_temp_access_token_validator,
        hyundai_oauth_result_store=fake_hyundai_oauth_result_store,
        app_login_result_store=fake_app_login_result_store,
        qr_session_store=fake_qr_session_store,
        vehicle_repository=fake_vehicle_repository,
        app_refresh_token_repository=fake_app_refresh_token_repository,
        app_token_issuer=fake_app_token_issuer,
        refresh_token_hasher=fake_refresh_token_hasher,
    )


@pytest.fixture
def valid_app_login_result(fake_app_login_result_store, fake_qr_session_store):
    fake_app_login_result_store.add_complete_result(VALID_SESSION_ID)
    fake_qr_session_store.add_session(
        session_id=VALID_SESSION_ID,
        vin_hash=VALID_VIN_HASH,
        status="pending",
    )


class TestConfirmVehicle:
    """UC-AUTH-005 - POST /auth/confirm-car"""

    def test_valid_car_id_and_vin_hash_saves_vehicle_and_issues_app_tokens(
        self,
        confirm_vehicle_service,
        fake_vehicle_repository,
        fake_app_token_issuer,
        fake_app_login_result_store,
        valid_app_login_result,
    ):
        """유효한 car_id와 vin_hash면 차량을 저장하고 app token을 발급한다."""
        command = ConfirmVehicleCommand(
            temp_access_token=VALID_TEMP_ACCESS_TOKEN,
            car_id=VALID_CAR_ID,
            vin_hash=VALID_VIN_HASH,
        )

        result = confirm_vehicle_service.execute(command)

        assert result.app_access_token == VALID_APP_ACCESS_TOKEN
        assert result.app_refresh_token == VALID_APP_REFRESH_TOKEN
        assert result.user_id == VALID_USER_ID
        assert result.name == VALID_USER_NAME
        assert result.car_id == VALID_CAR_ID
        assert result.car == VALID_CARS[0]
        assert fake_vehicle_repository.saved_vehicles == [
            {
                "user_id": VALID_USER_ID,
                "car": VALID_CARS[0],
            }
        ]
        assert fake_app_token_issuer.issue_calls == [
            {
                "user_id": VALID_USER_ID,
                "car_id": VALID_CAR_ID,
            }
        ]
        assert fake_app_login_result_store.used_sessions == [VALID_SESSION_ID]

    def test_refresh_token_plaintext_is_not_stored(
        self,
        confirm_vehicle_service,
        fake_app_refresh_token_repository,
        fake_refresh_token_hasher,
        valid_app_login_result,
    ):
        """refresh token 원문은 DB에 저장하지 않는다."""
        command = ConfirmVehicleCommand(
            temp_access_token=VALID_TEMP_ACCESS_TOKEN,
            car_id=VALID_CAR_ID,
            vin_hash=VALID_VIN_HASH,
        )

        confirm_vehicle_service.execute(command)

        saved_token = fake_app_refresh_token_repository.saved_token_hashes[0]
        assert saved_token["token_hash"] == VALID_REFRESH_TOKEN_HASH
        assert VALID_APP_REFRESH_TOKEN not in saved_token.values()
        assert fake_refresh_token_hasher.hash_calls == [VALID_APP_REFRESH_TOKEN]

    def test_hyundai_oauth_result_can_supply_vehicle_list(
        self,
        confirm_vehicle_service,
        fake_hyundai_oauth_result_store,
        fake_qr_session_store,
    ):
        """hyundai_oauth 결과에 차량 목록이 있어도 차량 확정에 사용할 수 있다."""
        fake_hyundai_oauth_result_store.add_result(VALID_SESSION_ID)
        fake_qr_session_store.add_session(
            session_id=VALID_SESSION_ID,
            vin_hash=VALID_VIN_HASH,
            status="pending",
        )
        command = ConfirmVehicleCommand(
            temp_access_token=VALID_TEMP_ACCESS_TOKEN,
            car_id=VALID_CAR_ID,
            vin_hash=VALID_VIN_HASH,
        )

        result = confirm_vehicle_service.execute(command)

        assert result.car == VALID_CARS[0]

    def test_expired_temp_token_raises_error(
        self,
        confirm_vehicle_service,
    ):
        """임시 token이 만료되면 실패한다."""
        command = ConfirmVehicleCommand(
            temp_access_token=EXPIRED_TEMP_ACCESS_TOKEN,
            car_id=VALID_CAR_ID,
            vin_hash=VALID_VIN_HASH,
        )

        with pytest.raises(ValueError) as exc_info:
            confirm_vehicle_service.execute(command)

        assert str(exc_info.value) == ERROR_TEMP_TOKEN_EXPIRED

    def test_car_id_not_in_list_raises_error(
        self,
        confirm_vehicle_service,
        fake_vehicle_repository,
        fake_app_refresh_token_repository,
        valid_app_login_result,
    ):
        """차량 목록에 없는 car_id면 실패한다."""
        command = ConfirmVehicleCommand(
            temp_access_token=VALID_TEMP_ACCESS_TOKEN,
            car_id=OTHER_CAR_ID,
            vin_hash=VALID_VIN_HASH,
        )

        with pytest.raises(ValueError) as exc_info:
            confirm_vehicle_service.execute(command)

        assert str(exc_info.value) == ERROR_CAR_ID_NOT_IN_LIST
        assert fake_vehicle_repository.saved_vehicles == []
        assert fake_app_refresh_token_repository.saved_token_hashes == []

    def test_vin_hash_mismatch_raises_error(
        self,
        confirm_vehicle_service,
        fake_vehicle_repository,
        fake_app_refresh_token_repository,
        valid_app_login_result,
    ):
        """vin_hash가 QR 세션의 vin_hash와 다르면 실패한다."""
        command = ConfirmVehicleCommand(
            temp_access_token=VALID_TEMP_ACCESS_TOKEN,
            car_id=VALID_CAR_ID,
            vin_hash=OTHER_VIN_HASH,
        )

        with pytest.raises(ValueError) as exc_info:
            confirm_vehicle_service.execute(command)

        assert str(exc_info.value) == ERROR_VIN_HASH_MISMATCH
        assert fake_vehicle_repository.saved_vehicles == []
        assert fake_app_refresh_token_repository.saved_token_hashes == []

    def test_expired_qr_session_raises_error(
        self,
        confirm_vehicle_service,
        fake_app_login_result_store,
        fake_qr_session_store,
    ):
        """QR 세션이 만료되면 실패한다."""
        fake_app_login_result_store.add_complete_result(VALID_SESSION_ID)
        fake_qr_session_store.add_session(
            session_id=VALID_SESSION_ID,
            vin_hash=VALID_VIN_HASH,
            status="expired",
        )
        command = ConfirmVehicleCommand(
            temp_access_token=VALID_TEMP_ACCESS_TOKEN,
            car_id=VALID_CAR_ID,
            vin_hash=VALID_VIN_HASH,
        )

        with pytest.raises(ValueError) as exc_info:
            confirm_vehicle_service.execute(command)

        assert str(exc_info.value) == ERROR_QR_SESSION_EXPIRED
