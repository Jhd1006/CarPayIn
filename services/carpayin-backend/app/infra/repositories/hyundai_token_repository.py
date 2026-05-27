from sqlalchemy.orm import Session

from app.infra.db.models import HyundaiToken


class SqlAlchemyHyundaiTokenRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_token(self, *, user_id: str, encrypted_refresh_token: str) -> None:
        token = self.session.get(HyundaiToken, user_id)
        if token is None:
            token = HyundaiToken(user_id=user_id)
            self.session.add(token)

        token.hyundai_refresh_token_encrypted = encrypted_refresh_token
        self.session.commit()

    def find_by_user_id(self, user_id: str) -> dict | None:
        token = self.session.get(HyundaiToken, user_id)
        if token is None:
            return None

        return {
            "user_id": token.user_id,
            "encrypted_refresh_token": token.hyundai_refresh_token_encrypted,
        }
