from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.infra.db.models import AppRefreshToken


APP_REFRESH_TOKEN_TTL_DAYS = 30


class SqlAlchemyAppRefreshTokenRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_token_hash(
        self,
        *,
        token_hash: str,
        user_id: str,
        car_id: str,
        expires_at: datetime | None = None,
    ) -> None:
        token = AppRefreshToken(
            refresh_token_hash=token_hash,
            user_id=user_id,
            car_id=car_id,
            status="active",
            expires_at=expires_at
            or datetime.now(timezone.utc) + timedelta(days=APP_REFRESH_TOKEN_TTL_DAYS),
        )
        self.session.add(token)
        self.session.commit()

    def find_by_hash(self, token_hash: str) -> dict | None:
        token = self.session.get(AppRefreshToken, token_hash)
        if token is None:
            return None

        return {
            "token_hash": token.refresh_token_hash,
            "user_id": token.user_id,
            "car_id": token.car_id,
            "status": token.status,
            "expires_at": token.expires_at,
        }

    def mark_expired(self, token_hash: str) -> None:
        token = self.session.get(AppRefreshToken, token_hash)
        if token is None:
            raise LookupError("refresh_token_not_found")

        token.status = "expired"
        self.session.commit()
