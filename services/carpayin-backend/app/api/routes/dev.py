import os
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.api.deps import get_current_user, notification_publisher
from app.infra.db.session import get_db_session
from app.infra.redis import redis_client

router = APIRouter(tags=["Dev"])


@router.post("/dev/reset")
def dev_reset(session: Session = Depends(get_db_session)) -> dict:
    if os.getenv("APP_ENV", "local").strip().lower() in {"prod", "production"}:
        return {"status": "forbidden", "message": "not allowed in production"}

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


@router.post("/dev/mock-payment-notification")
def mock_payment_notification(
    current_user: dict = Depends(get_current_user),
) -> dict:
    car_id = current_user["car_id"]
    notification_publisher.publish_payment_notification(
        session_id="sess_dev_001",
        car_id=car_id,
        lot_id="LOT_GANGNAM_01",
        tx_id=f"dev_tx_{uuid.uuid4().hex[:12]}",
        amount=3000,
        currency="KRW",
        approval_no="DEV-APPROVED",
    )
    return {"status": "ok"}
