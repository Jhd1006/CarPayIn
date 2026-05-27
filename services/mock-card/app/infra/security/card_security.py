import hashlib
import hmac
import os
from datetime import datetime, timezone


class MockCardValidator:
    def validate_card(self, card_number: str, expiry: str, cvc: str) -> bool:
        if len(card_number) != 16 or not card_number.isdigit():
            return False
        if len(cvc) != 3 or not cvc.isdigit():
            return False

        try:
            month_text, year_text = expiry.split("/")
            expiry_month = datetime(
                2000 + int(year_text),
                int(month_text),
                1,
                tzinfo=timezone.utc,
            )
        except (TypeError, ValueError):
            return False

        now = datetime.now(timezone.utc)
        current_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        return expiry_month >= current_month


class MockCardEncryptor:
    def __init__(self, secret: str | None = None):
        self.secret = (
            secret or os.getenv("MOCK_CARD_SECURITY_SECRET", "mock-card-dev-secret")
        ).encode()

    def encrypt_card_number(self, card_number: str) -> str:
        return self._digest("card-number", card_number)

    def hash_cvc(self, cvc: str) -> str:
        return self._digest("cvc", cvc)

    def _digest(self, purpose: str, value: str) -> str:
        return hmac.new(
            self.secret,
            f"{purpose}:{value}".encode(),
            hashlib.sha256,
        ).hexdigest()
