from uuid import uuid4

from app.infra.db.models import User, Vehicle
from app.infra.db.session import SessionLocal
from app.infra.repositories.user_repository import SqlAlchemyUserRepository
from app.infra.repositories.vehicle_repository import SqlAlchemyVehicleRepository


def test_user_and_vehicle_can_be_saved_and_loaded_from_postgres():
    session = SessionLocal()
    user_repository = SqlAlchemyUserRepository(session)
    vehicle_repository = SqlAlchemyVehicleRepository(session)

    unique_id = uuid4().hex
    user_id = f"integration-user-{unique_id}"
    car_id = f"integration-car-{unique_id}"
    initial_plate = f"T{unique_id[:7]}"
    updated_plate = f"U{unique_id[:7]}"

    try:
        user_repository.upsert_user(user_id=user_id, name="Integration Test User")
        vehicle_repository.upsert_vehicle(
            user_id=user_id,
            car={
                "car_id": car_id,
                "car_sellname": "IONIQ 5",
                "plate": initial_plate,
            },
        )

        loaded_vehicle = vehicle_repository.get_vehicle_by_car_id(car_id)

        assert loaded_vehicle is not None
        assert loaded_vehicle["car_id"] == car_id
        assert loaded_vehicle["user_id"] == user_id
        assert loaded_vehicle["car_sellname"] == "IONIQ 5"
        assert loaded_vehicle["plate"] == initial_plate
        assert vehicle_repository.exists(user_id=user_id, car_id=car_id)
        assert vehicle_repository.exists_by_car_id(car_id=car_id)

        vehicle_repository.update_plate(car_id=car_id, plate=updated_plate)
        assert vehicle_repository.get_vehicle_by_car_id(car_id)["plate"] == updated_plate
    finally:
        session.rollback()
        vehicle = session.get(Vehicle, car_id)
        if vehicle is not None:
            session.delete(vehicle)

        user = session.get(User, user_id)
        if user is not None:
            session.delete(user)

        session.commit()
        session.close()
