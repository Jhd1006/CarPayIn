from dataclasses import dataclass


@dataclass(frozen=True)
class ConfirmVehicleCommand:
    temp_access_token: str
    car_id: str
    vin_hash: str


@dataclass(frozen=True)
class ConfirmVehicleResult:
    app_access_token: str
    app_refresh_token: str
    user_id: str
    name: str
    car_id: str
    car: dict


class ConfirmVehicleService:
    def __init__(
        self,
        temp_access_token_validator,
        hyundai_oauth_result_store,
        app_login_result_store,
        qr_session_store,
        vehicle_repository,
        app_refresh_token_repository,
        app_token_issuer,
        refresh_token_hasher,
    ):
        self.temp_access_token_validator = temp_access_token_validator
        self.hyundai_oauth_result_store = hyundai_oauth_result_store
        self.app_login_result_store = app_login_result_store
        self.qr_session_store = qr_session_store
        self.vehicle_repository = vehicle_repository
        self.app_refresh_token_repository = app_refresh_token_repository
        self.app_token_issuer = app_token_issuer
        self.refresh_token_hasher = refresh_token_hasher

    def execute(self, command: ConfirmVehicleCommand) -> ConfirmVehicleResult:
        if not command.temp_access_token:
            raise ValueError("temp_access_token is required")

        if not command.car_id:
            raise ValueError("car_id is required")

        if not command.vin_hash:
            raise ValueError("vin_hash is required")

        token_data = self.temp_access_token_validator.validate_and_extract(
            command.temp_access_token
        )
        user_id = token_data["user_id"]
        session_id = token_data["session_id"]

        login_result = self._get_login_result(session_id)
        if not login_result:
            raise ValueError("login_result_not_found")

        selected_car = self._find_car(login_result.get("cars", []), command.car_id)
        if not selected_car:
            raise ValueError("car_id_not_in_list")

        qr_session = self.qr_session_store.get_session(session_id)
        if not qr_session or qr_session.get("status") == "expired":
            raise ValueError("qr_session_expired")

        if qr_session.get("vin_hash") != command.vin_hash:
            raise ValueError("vin_hash_mismatch")

        self.vehicle_repository.upsert_vehicle(
            user_id=user_id,
            car=selected_car,
        )

        issued_tokens = self.app_token_issuer.issue(
            user_id=user_id,
            car_id=command.car_id,
        )
        refresh_token_hash = self.refresh_token_hasher.hash(
            issued_tokens["refresh_token"]
        )
        self.app_refresh_token_repository.save_token_hash(
            token_hash=refresh_token_hash,
            user_id=user_id,
            car_id=command.car_id,
        )
        self.app_login_result_store.mark_used(session_id)

        return ConfirmVehicleResult(
            app_access_token=issued_tokens["access_token"],
            app_refresh_token=issued_tokens["refresh_token"],
            user_id=user_id,
            name=login_result["name"],
            car_id=command.car_id,
            car=selected_car,
        )

    def _get_login_result(self, session_id: str):
        return (
            self.hyundai_oauth_result_store.get_result(session_id)
            or self.app_login_result_store.get_result(session_id)
        )

    @staticmethod
    def _find_car(cars: list[dict], car_id: str):
        return next((car for car in cars if car.get("car_id") == car_id), None)
