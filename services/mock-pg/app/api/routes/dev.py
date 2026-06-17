import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.infra.db.session import get_db_session

router = APIRouter(tags=["Dev"])


@router.post("/dev/reset")
def dev_reset(session: Session = Depends(get_db_session)) -> dict:
    if os.getenv("APP_ENV", "local").strip().lower() in {"prod", "production"}:
        return {"status": "forbidden", "message": "not allowed in production"}

    session.execute(text("""
        TRUNCATE TABLE
            transactions,
            billing_keys
        CASCADE
    """))
    session.commit()

    return {"status": "ok", "message": "db cleared"}
