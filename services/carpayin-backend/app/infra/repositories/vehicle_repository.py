from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models import Vehicle


class SqlAlchemyVehicleRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_vehicle(self, *, user_id: str, car: dict) -> None:
        car_id = car["car_id"]
        vehicle = self.session.get(Vehicle, car_id)
        if vehicle is None:
            vehicle = Vehicle(car_id=car_id, user_id=user_id)
            self.session.add(vehicle)

        vehicle.user_id = user_id
        vehicle.car_sellname = car.get("car_sellname", car.get("model", ""))
        vehicle.plate = car.get("plate", "")
        self.session.commit()

    def get_vehicle_by_car_id(self, car_id: str) -> dict | None:
        vehicle = self.session.get(Vehicle, car_id)
        if vehicle is None:
            return None

        return {
            "car_id": vehicle.car_id,
            "user_id": vehicle.user_id,
            "car_sellname": vehicle.car_sellname,
            "plate": vehicle.plate,
        }

    def exists(self, *, user_id: str, car_id: str) -> bool:
        statement = select(Vehicle.car_id).where(
            Vehicle.user_id == user_id,
            Vehicle.car_id == car_id,
        )
        return self.session.scalar(statement) is not None

    def exists_by_car_id(self, *, car_id: str) -> bool:
        return self.session.get(Vehicle, car_id) is not None

    def update_plate(self, *, car_id: str, plate: str) -> None:
        vehicle = self.session.get(Vehicle, car_id)
        if vehicle is None:
            raise LookupError("vehicle_not_found")

        vehicle.plate = plate
        self.session.commit()
