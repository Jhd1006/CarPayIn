import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from cryptography.fernet import Fernet


TEMP_ACCESS_TOKEN_TTL_SECONDS = 15 * 60
APP_ACCESS_TOKEN_TTL_SECONDS = 60 * 60


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


class SignedTokenCodec:
    def __init__(self, secret: str):
        self._secret = secret.encode("utf-8")

    def issue(self, *, token_type: str, ttl_seconds: int, **claims: Any) -> str:
        payload = {
            **claims,
            "typ": token_type,
            "exp": int(time.time()) + ttl_seconds,
        }
        encoded_payload = _b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        signature = self._sign(encoded_payload)
        return f"{encoded_payload}.{signature}"

    def validate(
        self,
        token: str,
        *,
        token_type: str,
        expired_code: str = "invalid_token",
    ) -> dict:
        try:
            encoded_payload, signature = token.split(".", 1)
            if not hmac.compare_digest(signature, self._sign(encoded_payload)):
                raise ValueError("invalid_token")
            payload = json.loads(_b64decode(encoded_payload))
        except (binascii.Error, UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            raise ValueError("invalid_token")

        if not isinstance(payload, dict):
            raise ValueError("invalid_token")
        if payload.get("typ") != token_type:
            raise ValueError("invalid_token")
        if int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError(expired_code)
        return payload

    def _sign(self, encoded_payload: str) -> str:
        return hmac.new(
            self._secret,
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()


class TempAccessTokenIssuer:
    def __init__(self, codec: SignedTokenCodec):
        self._codec = codec

    def issue(self, *, user_id: str, session_id: str) -> str:
        return self._codec.issue(
            token_type="temp_access",
            ttl_seconds=TEMP_ACCESS_TOKEN_TTL_SECONDS,
            user_id=user_id,
            session_id=session_id,
        )


class TempAccessTokenValidator:
    def __init__(self, codec: SignedTokenCodec):
        self._codec = codec

    def validate_and_extract(self, token: str) -> dict:
        return self._codec.validate(
            token,
            token_type="temp_access",
            expired_code="temp_token_expired",
        )


class AppTokenIssuer:
    def __init__(self, codec: SignedTokenCodec):
        self._codec = codec

    def issue(self, *, user_id: str, car_id: str) -> dict:
        return {
            "access_token": self._codec.issue(
                token_type="app_access",
                ttl_seconds=APP_ACCESS_TOKEN_TTL_SECONDS,
                user_id=user_id,
                car_id=car_id,
            ),
            "refresh_token": secrets.token_urlsafe(48),
        }


class AppAccessTokenIssuer:
    def __init__(self, codec: SignedTokenCodec):
        self._codec = codec

    def issue(self, *, user_id: str, car_id: str) -> str:
        return self._codec.issue(
            token_type="app_access",
            ttl_seconds=APP_ACCESS_TOKEN_TTL_SECONDS,
            user_id=user_id,
            car_id=car_id,
        )


class AppAccessTokenValidator:
    def __init__(self, codec: SignedTokenCodec):
        self._codec = codec

    def validate_and_extract(self, token: str) -> dict:
        return self._codec.validate(token, token_type="app_access")


class RefreshTokenHasher:
    def __init__(self, secret: str):
        self._secret = secret.encode("utf-8")

    def hash(self, token: str) -> str:
        return hmac.new(
            self._secret,
            token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()


class RefreshTokenEncryptor:
    def __init__(self, secret: str):
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        self._cipher = Fernet(key)

    def encrypt(self, token: str) -> str:
        return self._cipher.encrypt(token.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        return self._cipher.decrypt(token.encode("ascii")).decode("utf-8")


class WebhookSignatureVerifier:
    def __init__(self, secret: str):
        self._secret = secret.encode("utf-8")

    def verify(self, *, order_id: str, signature: str) -> bool:
        expected = hmac.new(
            self._secret,
            order_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


class PmsAuthValidator:
    def __init__(self, token: str):
        self._token = token

    def validate(self, token: str) -> None:
        if not hmac.compare_digest(self._token, token):
            raise ValueError("pms_auth_failed")


def _requires_explicit_env() -> bool:
    return os.getenv("APP_ENV", "local").strip().lower() in {
        "aws",
        "staging",
        "prod",
        "production",
    }


def _secret_env(name: str, dev_default: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    if _requires_explicit_env():
        raise RuntimeError(f"{name} environment variable is required")
    return dev_default


def create_default_security_components() -> dict:
    token_secret = _secret_env("APP_TOKEN_SECRET", "carpayin-dev-token-secret")
    token_codec = SignedTokenCodec(token_secret)
    return {
        "temp_access_token_issuer": TempAccessTokenIssuer(token_codec),
        "temp_access_token_validator": TempAccessTokenValidator(token_codec),
        "app_token_issuer": AppTokenIssuer(token_codec),
        "app_access_token_issuer": AppAccessTokenIssuer(token_codec),
        "app_access_token_validator": AppAccessTokenValidator(token_codec),
        "refresh_token_hasher": RefreshTokenHasher(
            os.getenv("APP_REFRESH_TOKEN_HASH_SECRET", "").strip() or token_secret
        ),
        "refresh_token_encryptor": RefreshTokenEncryptor(
            _secret_env("HYUNDAI_TOKEN_ENCRYPTION_SECRET", "hyundai-dev-token-secret")
        ),
        "card_webhook_signature_verifier": WebhookSignatureVerifier(
            _secret_env("PG_WEBHOOK_SECRET", "mock-pg-webhook-secret")
        ),
        "pms_auth_validator": PmsAuthValidator(
            _secret_env("PMS_WEBHOOK_TOKEN", "pms-webhook-token")
        ),
    }
