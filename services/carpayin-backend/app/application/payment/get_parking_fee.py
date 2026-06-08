from dataclasses import dataclass


FEE_QUOTE_TTL_SECONDS = 15 * 60  # 15분 (테스트 중 결제 확인에 여유 시간 확보)


@dataclass(frozen=True)
class GetParkingFeeCommand:
    access_token: str
    session_id: str


@dataclass(frozen=True)
class GetParkingFeeResult:
    session_id: str
    lot_id: str
    amount: int
    duration: int
    currency: str
    entry_time: str
    status: str


class GetParkingFeeService:
    def __init__(
        self,
        token_validator,
        parking_session_repository,
        fee_quote_store,
        pms_client,
    ):
        self.token_validator = token_validator
        self.parking_session_repository = parking_session_repository
        self.fee_quote_store = fee_quote_store
        self.pms_client = pms_client

    def execute(self, command: GetParkingFeeCommand) -> GetParkingFeeResult:
        # 인증 및 car_id 추출
        token_data = self.token_validator.validate_and_extract(command.access_token)
        car_id = token_data["car_id"]

        # Redis quote 조회
        cached_quote = self.fee_quote_store.get_quote(command.session_id)
        if cached_quote:
            return GetParkingFeeResult(
                session_id=cached_quote["session_id"],
                lot_id=cached_quote["lot_id"],
                amount=cached_quote["amount"],
                duration=cached_quote["duration"],
                currency=cached_quote["currency"],
                entry_time=cached_quote["entry_time"],
                status=cached_quote["status"],
            )

        # DB에서 parking session 조회
        session = self.parking_session_repository.get_session_by_id(
            command.session_id
        )
        if not session:
            raise ValueError("session_not_found")

        if session["status"] != "active":
            raise ValueError("session_not_active")

        if session["car_id"] != car_id:
            raise ValueError("session_car_id_mismatch")

        # PMS에 요금 조회 (pms_session_id 함께 전달해 lot+plate 실패 시 폴백 가능)
        fee_data = self.pms_client.get_parking_fee(
            lot_id=session["lot_id"],
            plate=session["plate"],
            pms_session_id=session.get("pms_session_id"),
        )

        # Redis에 quote 저장
        self.fee_quote_store.save_quote(
            session_id=command.session_id,
            lot_id=session["lot_id"],
            amount=fee_data["amount"],
            duration=fee_data["duration"],
            currency=fee_data["currency"],
            entry_time=session["entry_time"],
            ttl_seconds=FEE_QUOTE_TTL_SECONDS,
        )

        return GetParkingFeeResult(
            session_id=command.session_id,
            lot_id=session["lot_id"],
            amount=fee_data["amount"],
            duration=fee_data["duration"],
            currency=fee_data["currency"],
            entry_time=session["entry_time"],
            status="active",
        )
