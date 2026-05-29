"""
입차 / 주차 세션 유스케이스 단위 테스트
UC-PARK-001: 사전 입차 알림 등록 (v2 - 2번째 md 파일 기준)
"""

import pytest

from app.application.parking.register_pre_notify import (
    RegisterPreNotifyCommand,
    RegisterPreNotifyService,
)


VALID_ACCESS_TOKEN = "at_valid_token_001"
VALID_CAR_ID = "car-001"
VALID_USER_ID = "user-001"
VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"
VALID_PLATE_NORMALIZED = "12가3456"
VALID_TRIGGER = "geofence"


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


class FakeVehicleRepository:
    def __init__(self):
        self.vehicles = {}

    def add_vehicle(self, car_id: str, plate: str = None):
        self.vehicles[car_id] = {
            "car_id": car_id,
            "plate": plate,
        }

    def get_vehicle_by_car_id(self, car_id: str):
        return self.vehicles.get(car_id)


class FakeBillingKeyRepository:
    def __init__(self):
        self.billing_keys = {}

    def add_active_billing_key(self, car_id: str):
        self.billing_keys[car_id] = {
            "car_id": car_id,
            "status": "active",
        }

    def has_active_billing_key(self, car_id: str) -> bool:
        key = self.billing_keys.get(car_id)
        return key is not None and key["status"] == "active"


class FakePreNotifyStore:
    def __init__(self):
        self.pre_notifies = {}

    def save_incoming(
        self, *, lot_id: str, plate: str, car_id: str, user_id: str, ttl_seconds: int
    ):
        key = f"{lot_id}:{plate}"
        self.pre_notifies[key] = {
            "lot_id": lot_id,
            "plate": plate,
            "car_id": car_id,
            "user_id": user_id,
            "status": "incoming",
            "ttl_seconds": ttl_seconds,
        }


class FakePmsClient:
    def __init__(self):
        self.pre_register_calls = []
        self.should_fail = False

    def pre_register_plate(self, *, lot_id: str, plate: str):
        if self.should_fail:
            raise Exception("PMS connection failed")
        self.pre_register_calls.append({"lot_id": lot_id, "plate": plate})


class FakePlateNormalizer:
    def normalize(self, plate: str) -> str:
        # 간단한 정규화: 공백 제거
        return plate.replace(" ", "").replace("-", "")


@pytest.fixture
def fake_token_validator():
    return FakeTokenValidator()


@pytest.fixture
def fake_vehicle_repository():
    return FakeVehicleRepository()


@pytest.fixture
def fake_billing_key_repository():
    return FakeBillingKeyRepository()


@pytest.fixture
def fake_pre_notify_store():
    return FakePreNotifyStore()


@pytest.fixture
def fake_pms_client():
    return FakePmsClient()


@pytest.fixture
def fake_plate_normalizer():
    return FakePlateNormalizer()


@pytest.fixture
def register_pre_notify_service(
    fake_token_validator,
    fake_vehicle_repository,
    fake_billing_key_repository,
    fake_pre_notify_store,
    fake_pms_client,
    fake_plate_normalizer,
):
    return RegisterPreNotifyService(
        token_validator=fake_token_validator,
        vehicle_repository=fake_vehicle_repository,
        billing_key_repository=fake_billing_key_repository,
        pre_notify_store=fake_pre_notify_store,
        pms_client=fake_pms_client,
        plate_normalizer=fake_plate_normalizer,
    )


class TestRegisterPreNotify:
    """UC-PARK-001 - POST /pre-notify"""

    def test_active_billing_key_stores_redis_and_calls_pms(
        self,
        register_pre_notify_service,
        fake_vehicle_repository,
        fake_billing_key_repository,
        fake_pre_notify_store,
        fake_pms_client,
    ):
        """active billing key가 있으면 Redis에 pre-notify를 저장하고 PMS를 호출한다."""
        fake_vehicle_repository.add_vehicle(VALID_CAR_ID, VALID_PLATE)
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)

        command = RegisterPreNotifyCommand(
            access_token=VALID_ACCESS_TOKEN,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
        )

        result = register_pre_notify_service.execute(command)

        # Redis 저장 확인
        key = f"{VALID_LOT_ID}:{VALID_PLATE_NORMALIZED}"
        assert key in fake_pre_notify_store.pre_notifies
        assert fake_pre_notify_store.pre_notifies[key]["status"] == "incoming"
        assert fake_pre_notify_store.pre_notifies[key]["car_id"] == VALID_CAR_ID
        assert fake_pre_notify_store.pre_notifies[key]["user_id"] == VALID_USER_ID

        # PMS 호출 확인
        assert len(fake_pms_client.pre_register_calls) == 1
        assert fake_pms_client.pre_register_calls[0]["lot_id"] == VALID_LOT_ID
        assert fake_pms_client.pre_register_calls[0]["plate"] == VALID_PLATE_NORMALIZED

        # 응답 확인
        assert result.status == "registered"
        assert result.car_id == VALID_CAR_ID
        assert result.lot_id == VALID_LOT_ID
        assert result.plate == VALID_PLATE_NORMALIZED

    def test_token_car_id_mismatch_raises_error(
        self,
        register_pre_notify_service,
        fake_vehicle_repository,
    ):
        """token의 car_id와 요청 car_id가 다르면 403을 반환한다."""
        fake_vehicle_repository.add_vehicle(VALID_CAR_ID, VALID_PLATE)

        command = RegisterPreNotifyCommand(
            access_token=VALID_ACCESS_TOKEN,
            car_id="different-car-id",  # 토큰의 car_id와 다름
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
        )

        with pytest.raises(ValueError) as exc_info:
            register_pre_notify_service.execute(command)

        assert str(exc_info.value) == "car_id_token_mismatch"

    def test_vehicle_not_found_raises_error(
        self,
        register_pre_notify_service,
    ):
        """차량이 없으면 400을 반환한다."""
        # vehicle_repository에 차량을 추가하지 않음

        command = RegisterPreNotifyCommand(
            access_token=VALID_ACCESS_TOKEN,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
        )

        with pytest.raises(ValueError) as exc_info:
            register_pre_notify_service.execute(command)

        assert str(exc_info.value) == "vehicle_not_found"

    def test_plate_not_registered_raises_error(
        self,
        register_pre_notify_service,
        fake_vehicle_repository,
    ):
        """차량번호가 없으면 400을 반환한다."""
        fake_vehicle_repository.add_vehicle(VALID_CAR_ID, plate=None)

        command = RegisterPreNotifyCommand(
            access_token=VALID_ACCESS_TOKEN,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
        )

        with pytest.raises(ValueError) as exc_info:
            register_pre_notify_service.execute(command)

        assert str(exc_info.value) == "plate_not_registered"

    def test_plate_mismatch_raises_error(
        self,
        register_pre_notify_service,
        fake_vehicle_repository,
    ):
        """요청 차량번호와 등록 차량번호가 불일치하면 400을 반환한다."""
        fake_vehicle_repository.add_vehicle(VALID_CAR_ID, "99나9999")

        command = RegisterPreNotifyCommand(
            access_token=VALID_ACCESS_TOKEN,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,  # DB에 등록된 것과 다름
        )

        with pytest.raises(ValueError) as exc_info:
            register_pre_notify_service.execute(command)

        assert str(exc_info.value) == "plate_mismatch"

    def test_no_active_billing_key_raises_error_and_does_not_call_pms(
        self,
        register_pre_notify_service,
        fake_vehicle_repository,
        fake_pms_client,
    ):
        """billing key가 없으면 400을 반환하고 PMS를 호출하지 않는다."""
        fake_vehicle_repository.add_vehicle(VALID_CAR_ID, VALID_PLATE)
        # billing_key_repository에 키를 추가하지 않음

        command = RegisterPreNotifyCommand(
            access_token=VALID_ACCESS_TOKEN,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
        )

        with pytest.raises(ValueError) as exc_info:
            register_pre_notify_service.execute(command)

        assert str(exc_info.value) == "no_active_billing_key"
        assert len(fake_pms_client.pre_register_calls) == 0

    def test_pms_pre_register_failure_raises_error(
        self,
        register_pre_notify_service,
        fake_vehicle_repository,
        fake_billing_key_repository,
        fake_pms_client,
    ):
        """PMS 사전 등록에 실패한 경우 400을 반환한다."""
        fake_vehicle_repository.add_vehicle(VALID_CAR_ID, VALID_PLATE)
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)
        fake_pms_client.should_fail = True

        command = RegisterPreNotifyCommand(
            access_token=VALID_ACCESS_TOKEN,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
        )

        with pytest.raises(Exception) as exc_info:
            register_pre_notify_service.execute(command)

        assert "PMS connection failed" in str(exc_info.value)
