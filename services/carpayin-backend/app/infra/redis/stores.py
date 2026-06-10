import json
from datetime import datetime, timedelta, timezone

from redis import Redis


class _RedisJsonStore:
    def __init__(self, client: Redis):
        self.client = client

    def _save(self, key: str, value: dict, ttl_seconds: int) -> None:
        now = datetime.now(timezone.utc)
        payload = {
            **value,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
        }
        self.client.set(key, json.dumps(payload), ex=ttl_seconds)

    def _get(self, key: str) -> dict | None:
        raw_value = self.client.get(key)
        return json.loads(raw_value) if raw_value is not None else None

    def _update(self, key: str, **fields) -> dict | None:
        payload = self._get(key)
        if payload is None:
            return None

        payload.update(fields)
        ttl_seconds = self.client.ttl(key)
        if ttl_seconds > 0:
            self.client.set(key, json.dumps(payload), ex=ttl_seconds)
        else:
            self.client.set(key, json.dumps(payload))
        return payload


class RedisQrSessionStore(_RedisJsonStore):
    def save_pending_session(
        self, *, session_id: str, vin_hash: str, ttl_seconds: int
    ) -> None:
        self._save(
            f"qr_session:{session_id}",
            {"vin_hash": vin_hash, "status": "pending", "debug_message": ""},
            ttl_seconds,
        )

    def get_session(self, session_id: str) -> dict | None:
        return self._get(f"qr_session:{session_id}")

    def mark_failed(self, *, session_id: str, reason: str) -> None:
        self._update(
            f"qr_session:{session_id}",
            status="failed",
            debug_message=reason,
        )


class RedisOAuthStateStore(_RedisJsonStore):
    def save_oauth_state(
        self, *, oauth_state: str, session_id: str, ttl_seconds: int
    ) -> None:
        self._save(
            f"oauth_state:{oauth_state}",
            {"session_id": session_id, "status": "pending"},
            ttl_seconds,
        )

    def get_session_id(self, oauth_state: str) -> str | None:
        state = self._get(f"oauth_state:{oauth_state}")
        if state is None or state.get("status") != "pending":
            return None
        return state["session_id"]

    def mark_used(self, oauth_state: str) -> None:
        self._update(f"oauth_state:{oauth_state}", status="used")


class RedisHyundaiOAuthResultStore(_RedisJsonStore):
    def save_result(
        self,
        *,
        session_id: str,
        user_id: str,
        name: str,
        cars: list[dict],
        temp_access_token: str,
        ttl_seconds: int,
    ) -> None:
        self._save(
            f"hyundai_oauth:{session_id}",
            {
                "user_id": user_id,
                "name": name,
                "cars": cars,
                "temp_access_token": temp_access_token,
            },
            ttl_seconds,
        )

    def get_result(self, session_id: str) -> dict | None:
        return self._get(f"hyundai_oauth:{session_id}")


class RedisAppLoginResultStore(_RedisJsonStore):
    def save_result(
        self,
        *,
        session_id: str,
        status: str,
        user_id: str,
        name: str,
        cars: list[dict],
        temp_access_token: str,
        ttl_seconds: int,
    ) -> None:
        self._save(
            f"app_login_result:{session_id}",
            {
                "status": status,
                "user_id": user_id,
                "name": name,
                "cars": cars,
                "temp_access_token": temp_access_token,
            },
            ttl_seconds,
        )

    def get_result(self, session_id: str) -> dict | None:
        return self._get(f"app_login_result:{session_id}")

    def mark_used(self, session_id: str) -> None:
        self.client.delete(f"app_login_result:{session_id}")


class RedisCardOrderStore(_RedisJsonStore):
    def save_pending(
        self,
        *,
        order_id: str,
        user_id: str,
        car_id: str,
        ttl_seconds: int,
    ) -> None:
        self._save(
            f"mock_pg_card_register:{order_id}",
            {
                "order_id": order_id,
                "user_id": user_id,
                "car_id": car_id,
                "status": "pending",
            },
            ttl_seconds,
        )

    def get_pending(self, *, order_id: str) -> dict | None:
        order = self.get_order(order_id=order_id)
        if order is None or order.get("status") != "pending":
            return None
        return order

    def get_order(self, *, order_id: str) -> dict | None:
        return self._get(f"mock_pg_card_register:{order_id}")

    def mark_complete(self, *, order_id: str) -> None:
        self._update(f"mock_pg_card_register:{order_id}", status="complete")

    def delete(self, *, order_id: str) -> None:
        self.client.delete(f"mock_pg_card_register:{order_id}")


class RedisPreNotifyStore(_RedisJsonStore):
    def save_incoming(
        self,
        *,
        lot_id: str,
        plate: str,
        car_id: str,
        user_id: str,
        ttl_seconds: int,
    ) -> None:
        self._save(
            f"parking_pre_notify:{lot_id}:{plate}",
            {
                "user_id": user_id,
                "car_id": car_id,
                "lot_id": lot_id,
                "plate": plate,
                "status": "incoming",
            },
            ttl_seconds,
        )

    def get_pre_notify(self, lot_id: str, plate: str) -> dict | None:
        return self._get(f"parking_pre_notify:{lot_id}:{plate}")

    def delete_pre_notify(self, lot_id: str, plate: str) -> None:
        self.client.delete(f"parking_pre_notify:{lot_id}:{plate}")


class RedisFeeQuoteStore(_RedisJsonStore):
    def save_quote(
        self,
        *,
        session_id: str,
        lot_id: str,
        amount: int,
        duration: int,
        currency: str,
        entry_time: str,
        ttl_seconds: int,
    ) -> None:
        self._save(
            f"parking_fee_quote:{session_id}",
            {
                "session_id": session_id,
                "lot_id": lot_id,
                "amount": amount,
                "duration": duration,
                "currency": currency,
                "entry_time": entry_time,
                "status": "active",
            },
            ttl_seconds,
        )

    def get_quote(self, session_id: str) -> dict | None:
        return self._get(f"parking_fee_quote:{session_id}")


class RedisEntryNotifyRetryStore(_RedisJsonStore):
    def record_retry_event(
        self,
        *,
        car_id: str,
        session_id: str,
        lot_id: str,
        entry_time: str,
        ttl_seconds: int = 60 * 60,
    ) -> None:
        self._save(
            f"entry_notify_retry:{session_id}",
            {
                "car_id": car_id,
                "session_id": session_id,
                "lot_id": lot_id,
                "entry_time": entry_time,
                "status": "pending",
            },
            ttl_seconds,
        )

    def get_retry_event(self, session_id: str) -> dict | None:
        return self._get(f"entry_notify_retry:{session_id}")

    def clear_retry_event(self, session_id: str) -> None:
        self.client.delete(f"entry_notify_retry:{session_id}")


class RedisPaymentNotifyRetryStore(_RedisJsonStore):
    def record_retry_event(
        self,
        *,
        event_type: str,
        tx_id: str,
        payload: dict,
        reason: str,
        ttl_seconds: int = 7 * 24 * 60 * 60,
    ) -> None:
        self._save(
            f"pms_payment_retry:{tx_id}",
            {
                "event_type": event_type,
                "tx_id": tx_id,
                "payload": payload,
                "reason": reason,
                "status": "pending",
            },
            ttl_seconds,
        )

    def get_retry_event(self, tx_id: str) -> dict | None:
        return self._get(f"pms_payment_retry:{tx_id}")

    def clear_retry_event(self, tx_id: str) -> None:
        self.client.delete(f"pms_payment_retry:{tx_id}")
