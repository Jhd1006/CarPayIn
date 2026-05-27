from uuid import uuid4

from fastapi.testclient import TestClient

from app.infra.db.models import Card, CardToken, Tx, User
from app.infra.db.session import SessionLocal
from app.main import app


def test_verify_then_charge_uses_mock_card_database_dependencies():
    unique_id = uuid4().hex
    user_id = f"api-card-user-{unique_id}"
    idempotency_key = f"api-card-idempotency-{unique_id}"
    card_token = None
    tx_id = None

    try:
        with TestClient(app) as client:
            verify_response = client.post(
                "/cards/verify",
                json={
                    "user_id": user_id,
                    "card_number": "4111111111111111",
                    "expiry": "12/30",
                    "cvc": "123",
                },
            )
            assert verify_response.status_code == 200
            card_token = verify_response.json()["card_token"]
            assert verify_response.json()["last_four"] == "1111"

            duplicate_response = client.post(
                "/cards/verify",
                json={
                    "user_id": user_id,
                    "card_number": "4111111111111111",
                    "expiry": "12/30",
                    "cvc": "123",
                },
            )
            assert duplicate_response.json()["card_token"] == card_token

            charge_response = client.post(
                "/cards/charge",
                json={
                    "card_token": card_token,
                    "amount": 5000,
                    "currency": "KRW",
                    "idempotency_key": idempotency_key,
                },
            )
            assert charge_response.status_code == 200
            assert charge_response.json()["status"] == "success"
            tx_id = charge_response.json()["tx_id"]

        session = SessionLocal()
        try:
            token = session.get(CardToken, card_token)
            assert token is not None
            card = session.get(Card, token.card_id)
            assert card is not None
            assert card.encrypted_card_num != "4111111111111111"
            assert card.cvc_hmac != "123"
            assert session.get(Tx, tx_id).status == "success"
        finally:
            session.close()
    finally:
        session = SessionLocal()
        try:
            if tx_id is not None:
                transaction = session.get(Tx, tx_id)
                if transaction is not None:
                    session.delete(transaction)
            if card_token is not None:
                token = session.get(CardToken, card_token)
                card_id = token.card_id if token is not None else None
                if token is not None:
                    session.delete(token)
                session.flush()
                if card_id is not None:
                    card = session.get(Card, card_id)
                    if card is not None:
                        session.delete(card)
            user = session.get(User, user_id)
            if user is not None:
                session.delete(user)
            session.commit()
        finally:
            session.close()
