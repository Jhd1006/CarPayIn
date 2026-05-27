from dataclasses import dataclass


PRE_NOTIFY_TTL_SECONDS = 60 * 60


@dataclass(frozen=True)
class RegisterPreNotifyCommand:
    access_token: str
    car_id: str
    lot_id: str
    plate: str


@dataclass(frozen=True)
class RegisterPreNotifyResult:
    status: str
    car_id: str
    lot_id: str
    plate: str


class RegisterPreNotifyService:
    def __init__(
        self,
        token_validator,
        vehicle_repository,
        billing_key_repository,
        pre_notify_store,
        pms_client,
        plate_normalizer,
    ):
        self.token_validator = token_validator
        self.vehicle_repository = vehicle_repository
        self.billing_key_repository = billing_key_repository
        self.pre_notify_store = pre_notify_store
        self.pms_client = pms_client
        self.plate_normalizer = plate_normalizer

    def execute(self, command: RegisterPreNotifyCommand) -> RegisterPreNotifyResult:
        # 인증 및 car_id 추출
        token_data = self.token_validator.validate_and_extract(command.access_token)
        token_car_id = token_data["car_id"]

        # 요청 car_id와 토큰 car_id 일치 검증
        if command.car_id != token_car_id:
            raise ValueError("car_id_token_mismatch")
        
        # 차량 조회
        vehicle = self.vehicle_repository.get_vehicle_by_car_id(command.car_id)
        if not vehicle:
            raise ValueError("vehicle_not_found")

        # 차량번호 확인
        db_plate = vehicle.get("plate")
        if not db_plate:
            raise ValueError("plate_not_registered")

        # 차량번호 정규화 및 DB 차량번호와 비교
        normalized_request_plate = self.plate_normalizer.normalize(command.plate)
        normalized_db_plate = self.plate_normalizer.normalize(db_plate)
        if normalized_request_plate != normalized_db_plate:
            raise ValueError("plate_mismatch")
        
        # active billing key 확인
        if not self.billing_key_repository.has_active_billing_key(command.car_id):
            raise ValueError("no_active_billing_key")

        # Redis에 pre-notify 저장
        self.pre_notify_store.save_incoming(
            lot_id=command.lot_id,
            plate=normalized_request_plate,
            car_id=command.car_id,
            user_id=token_data["user_id"],
            ttl_seconds=PRE_NOTIFY_TTL_SECONDS,
        )

        # PMS에 사전 등록 요청
        self.pms_client.pre_register_plate(
            lot_id=command.lot_id,
            plate=normalized_request_plate
        )

        return RegisterPreNotifyResult(
            status="registered",
            car_id=command.car_id,
            lot_id=command.lot_id,
            plate=normalized_request_plate,
        )
