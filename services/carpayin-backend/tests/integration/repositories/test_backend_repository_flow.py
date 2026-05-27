from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.infra.db.models import (
    AppRefreshToken,
    HyundaiToken,
    ParkingSession,
    Transaction,
    User,
    Vehicle,
    VehicleBillingKey,
)
from app.infra.db.session import SessionLocal
from app.infra.repositories.app_refresh_token_repository import (
    SqlAlchemyAppRefreshTokenRepository,
)
from app.infra.repositories.billing_key_repository import SqlAlchemyBillingKeyRepository
from app.infra.repositories.hyundai_token_repository import SqlAlchemyHyundaiTokenRepository
from app.infra.repositories.parking_session_repository import (
    SqlAlchemyParkingSessionRepository,
)
from app.infra.repositories.transaction_repository import SqlAlchemyTransactionRepository
from app.infra.repositories.user_repository import SqlAlchemyUserRepository
from app.infra.repositories.vehicle_repository import SqlAlchemyVehicleRepository


def test_all_backend_business_tables_can_store_and_load_data_from_postgres():
    session = SessionLocal()
    user_repository = SqlAlchemyUserRepository(session)
    vehicle_repository = SqlAlchemyVehicleRepository(session)
    billing_key_repository = SqlAlchemyBillingKeyRepository(session)
    parking_session_repository = SqlAlchemyParkingSessionRepository(session)
    transaction_repository = SqlAlchemyTransactionRepository(session)
    app_refresh_token_repository = SqlAlchemyAppRefreshTokenRepository(session)
    hyundai_token_repository = SqlAlchemyHyundaiTokenRepository(session)

    unique_id = uuid4().hex
    user_id = f"integration-user-{unique_id}"
    car_id = f"integration-car-{unique_id}"
    billing_key = f"billing-key-{unique_id}"
    parking_session_id = str(uuid4())
    pms_session_id = f"pms-session-{unique_id}"
    transaction_id = str(uuid4())
    idempotency_key = f"idempotency-{unique_id}"
    refresh_token_hash = unique_id * 2
    entry_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    try:
        user_repository.upsert_user(user_id=user_id, name="Integration Test User")
        vehicle_repository.upsert_vehicle(
            user_id=user_id,
            car={
                "car_id": car_id,
                "car_sellname": "IONIQ 5",
                "plate": "12TEST34",
            },
        )

        hyundai_token_repository.upsert_token(
            user_id=user_id,
            encrypted_refresh_token=f"encrypted-{unique_id}",
        )
        stored_hyundai_token = hyundai_token_repository.find_by_user_id(user_id)
        assert stored_hyundai_token["encrypted_refresh_token"] == f"encrypted-{unique_id}"

        app_refresh_token_repository.save_token_hash(
            token_hash=refresh_token_hash,
            user_id=user_id,
            car_id=car_id,
            expires_at=expires_at,
        )
        stored_refresh_token = app_refresh_token_repository.find_by_hash(
            refresh_token_hash
        )
        assert stored_refresh_token["user_id"] == user_id
        assert stored_refresh_token["car_id"] == car_id
        assert stored_refresh_token["status"] == "active"

        billing_key_repository.upsert(
            car_id=car_id,
            billing_key=billing_key,
            card_last_four="1234",
        )
        assert billing_key_repository.has_active_billing_key(car_id)
        assert (
            billing_key_repository.get_active_billing_key(car_id)["billing_key"]
            == billing_key
        )

        parking_session_repository.create_session(
            session_id=parking_session_id,
            pms_session_id=pms_session_id,
            car_id=car_id,
            plate="12TEST34",
            lot_id="lot-001",
            entry_time=entry_time,
        )
        stored_session = parking_session_repository.get_session_by_id(
            parking_session_id
        )
        assert stored_session["status"] == "active"
        assert (
            parking_session_repository.get_session_by_pms_session_id(
                pms_session_id
            )["session_id"]
            == parking_session_id
        )
        assert (
            parking_session_repository.get_active_session_by_car_id(car_id)[
                "session_id"
            ]
            == parking_session_id
        )

        transaction_repository.create_pending_transaction(
            tx_id=transaction_id,
            idempotency_key=idempotency_key,
            session_id=parking_session_id,
            amount=5000,
            currency="KRW",
            billing_key=billing_key,
        )
        stored_transaction = transaction_repository.get_transaction_by_idempotency_key(
            idempotency_key
        )
        assert stored_transaction["status"] == "pending"
        assert stored_transaction["car_id"] == car_id

        transaction_repository.update_transaction_status(
            idempotency_key,
            "success",
            pg_tx_id=f"pg-tx-{unique_id}",
            approval_no="APPR1234",
        )
        parking_session_repository.update_session_status(parking_session_id, "completed")
        app_refresh_token_repository.mark_expired(refresh_token_hash)

        assert (
            transaction_repository.get_transaction_by_id(transaction_id)["status"]
            == "success"
        )
        assert (
            parking_session_repository.get_session_by_id(parking_session_id)["status"]
            == "completed"
        )
        assert (
            parking_session_repository.get_session_by_id(parking_session_id)["exit_time"]
            is not None
        )
        assert (
            app_refresh_token_repository.find_by_hash(refresh_token_hash)["status"]
            == "expired"
        )
    finally:
        session.rollback()
        for model, primary_key in (
            (Transaction, UUID(transaction_id)),
            (ParkingSession, UUID(parking_session_id)),
            (AppRefreshToken, refresh_token_hash),
            (HyundaiToken, user_id),
            (VehicleBillingKey, car_id),
            (Vehicle, car_id),
            (User, user_id),
        ):
            record = session.get(model, primary_key)
            if record is not None:
                session.delete(record)
        session.commit()
        session.close()
