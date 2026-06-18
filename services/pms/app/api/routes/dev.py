from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.infra.db.session import get_db_session
from app.infra.redis.client import redis_client
from app.infra.redis.stores import RedisParkingSessionStore

router = APIRouter(tags=["Dev"])


@router.post("/dev/reset")
def dev_reset(session: Session = Depends(get_db_session)) -> dict:
    session.execute(text("""
        TRUNCATE TABLE
            payment_requests,
            parking_sessions
        CASCADE
    """))
    session.commit()

    redis_client.flushdb()

    return {"status": "ok", "message": "db and redis cleared"}


@router.post("/dev/mark-paid")
def dev_mark_paid(plate: str, lot_id: str) -> dict:
    store = RedisParkingSessionStore(redis_client)
    store.update_status(lot_id=lot_id, plate=plate, status="paid")
    return {"status": "ok", "lot_id": lot_id, "plate": plate}
