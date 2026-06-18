from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.infra.db.session import get_db_session

router = APIRouter(tags=["Dev"])


@router.post("/dev/reset")
def dev_reset(session: Session = Depends(get_db_session)) -> dict:
    session.execute(text("""
        TRUNCATE TABLE
            transactions,
            billing_keys
        CASCADE
    """))
    session.commit()

    return {"status": "ok", "message": "db cleared"}

@router.post("/dev/seed-billing-key")
def seed_billing_key(
    billing_key: str,
    session: Session = Depends(get_db_session),
) -> dict:
    session.execute(
        text("""
            INSERT INTO billing_keys (billing_key, order_id, card_token, card_last_four, status)
            VALUES (:billing_key, :order_id, :card_token, '0000', 'active')
            ON CONFLICT (billing_key) DO NOTHING
        """),
        {
            "billing_key": billing_key,
            "order_id":    f"load-order-{billing_key}",
            "card_token":  f"load-card-token-{billing_key}",
        },
    )
    session.commit()
    return {"status": "ok", "billing_key": billing_key}

