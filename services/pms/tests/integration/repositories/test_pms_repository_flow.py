from datetime import datetime, timezone
from uuid import uuid4

from app.infra.db.models import PMSParkingSession, PaymentRequest
from app.infra.db.session import SessionLocal
from app.infra.repositories.payment_request_repository import (
    SqlAlchemyPaymentRequestRepository,
)
from app.infra.repositories.pms_session_repository import SqlAlchemyPmsSessionRepository


def test_pms_tables_can_store_and_load_data_from_postgres():
    session = SessionLocal()
    pms_session_repository = SqlAlchemyPmsSessionRepository(session)
    payment_request_repository = SqlAlchemyPaymentRequestRepository(session)

    unique_id = uuid4().hex
    pms_session_id = f"integration-pms-session-{unique_id}"
    plate = f"P{unique_id[:7]}"
    idempotency_key = f"integration-pms-idempotency-{unique_id}"
    entry_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    try:
        pms_session_repository.create_session(
            pms_session_id=pms_session_id,
            lot_id="lot-001",
            plate=plate,
            entry_time=entry_time,
        )

        stored_session = pms_session_repository.get_active_session_by_plate(plate)
        assert stored_session["pms_session_id"] == pms_session_id
        assert (
            pms_session_repository.get_active_session_by_lot_and_plate(
                lot_id="lot-001", plate=plate
            )["status"]
            == "active"
        )

        stored_payment = payment_request_repository.save_payment_request(
            idempotency_key=idempotency_key,
            pms_session_id=pms_session_id,
            carpay_session_id=f"carpay-session-{unique_id}",
            tx_id=f"carpay-tx-{unique_id}",
            amount=5000,
            currency="KRW",
            approval_no="APPR1234",
        )
        assert stored_payment["status"] == "success"
        assert (
            payment_request_repository.get_by_idempotency_key(idempotency_key)[
                "pms_session_id"
            ]
            == pms_session_id
        )

        pms_session_repository.update_status(pms_session_id, "exited")
        assert pms_session_repository.get_session_by_id(pms_session_id)["status"] == "exited"
    finally:
        session.rollback()
        payment_request = session.query(PaymentRequest).filter_by(
            idempotency_key=idempotency_key
        ).one_or_none()
        if payment_request is not None:
            session.delete(payment_request)
        parking_session = session.get(PMSParkingSession, pms_session_id)
        if parking_session is not None:
            session.delete(parking_session)
        session.commit()
        session.close()
