from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models import Card, CardToken, User


class SqlAlchemyCardRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_user(self, *, user_id: str, name: str) -> None:
        user = self.session.get(User, user_id)
        if user is None:
            self.session.add(User(user_id=user_id, name=name))
        else:
            user.name = name
        self.session.commit()

    def save_card_with_token(
        self,
        *,
        user_id: str,
        encrypted_card_num: str,
        cvc_hmac: str,
        exp_month: int,
        exp_year: int,
        card_token: str,
    ) -> dict:
        statement = select(Card).where(
            Card.user_id == user_id,
            Card.encrypted_card_num == encrypted_card_num,
        )
        card = self.session.scalar(statement)
        if card is None:
            card = Card(
                user_id=user_id,
                encrypted_card_num=encrypted_card_num,
                cvc_hmac=cvc_hmac,
                exp_month=exp_month,
                exp_year=exp_year,
                status="active",
            )
            self.session.add(card)
            self.session.flush()

        token = self.session.get(CardToken, card_token)
        if token is None:
            token = CardToken(card_token=card_token, card_id=card.card_id, status="active")
            self.session.add(token)
        self.session.commit()
        return self.get_card_token(card_token)

    def get_card_token(self, card_token: str) -> dict | None:
        token = self.session.get(CardToken, card_token)
        if token is None:
            return None
        return {
            "card_token": token.card_token,
            "card_id": str(token.card_id),
            "status": token.status,
        }

    def get_by_user_and_encrypted_card(
        self, *, user_id: str, encrypted_card_num: str
    ) -> dict | None:
        statement = (
            select(CardToken)
            .join(Card, CardToken.card_id == Card.card_id)
            .where(
                Card.user_id == user_id,
                Card.encrypted_card_num == encrypted_card_num,
            )
        )
        token = self.session.scalar(statement)
        return self.get_card_token(token.card_token) if token is not None else None