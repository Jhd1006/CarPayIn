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

@router.post("/dev/seed-card-token")
def seed_card_token(
    card_token: str,
) -> dict:
    import os
    import httpx
    mock_card_base_url = os.getenv("MOCK_CARD_BASE_URL", "").rstrip("/")
    resp = httpx.post(
        f"{mock_card_base_url}/dev/seed-card-token",
        params={"card_token": card_token},
    )
    if resp.status_code != 200:
        return {"status": "failed", "detail": resp.text}
    return {"status": "ok", "card_token": card_token}
