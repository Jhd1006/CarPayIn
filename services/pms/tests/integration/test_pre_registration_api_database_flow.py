from uuid import uuid4

from fastapi.testclient import TestClient

from app.infra.db.models import PreRegistration
from app.infra.db.session import SessionLocal
from app.main import app


def test_pre_register_api_saves_plate_to_pms_database():
    unique_id = uuid4().hex
    lot_id = f"lot-api-{unique_id}"
    plate = f"A{unique_id[:7]}"

    try:
        with TestClient(app) as client:
            first_response = client.post(
                "/parking/pre-register",
                json={"lot_id": lot_id, "plate": plate},
            )
            second_response = client.post(
                "/parking/pre-register",
                json={"lot_id": lot_id, "plate": plate},
            )

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert first_response.json()["status"] == "registered"

        session = SessionLocal()
        try:
            registration = session.get(PreRegistration, (lot_id, plate))
            assert registration is not None
            assert registration.status == "pre_registered"
        finally:
            session.close()
    finally:
        session = SessionLocal()
        try:
            registration = session.get(PreRegistration, (lot_id, plate))
            if registration is not None:
                session.delete(registration)
                session.commit()
        finally:
            session.close()
