from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.infra.db.session import get_db_session
from app.infra.redis import redis_client

router = APIRouter(tags=["Dev"])


@router.post("/dev/reset")
def dev_reset(session: Session = Depends(get_db_session)) -> dict:
    session.execute(text("""
        TRUNCATE TABLE
            payment_notification_outbox,
            transactions,
            parking_sessions,
            app_refresh_tokens,
            vehicle_billing_keys,
            vehicles,
            users
        CASCADE
    """))
    session.commit()

    redis_client.flushdb()

    return {"status": "ok", "message": "db and redis cleared"}
