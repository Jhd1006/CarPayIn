from sqlalchemy.orm import Session

from app.infra.db.models import User


class SqlAlchemyUserRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_user(self, *, user_id: str, name: str) -> None:
        user = self.session.get(User, user_id)
        if user is None:
            user = User(user_id=user_id, name=name)
            self.session.add(user)
        else:
            user.name = name

        self.session.commit()

    def find_by_id(self, user_id: str) -> User | None:
        return self.session.get(User, user_id)
