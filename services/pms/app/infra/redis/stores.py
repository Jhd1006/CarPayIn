import json

from redis import Redis

PRE_REG_TTL_SECONDS = 60 * 60       # 1시간 - 사전등록 후 차가 안 오면 자동 만료
SESSION_TTL_SECONDS = 72 * 60 * 60  # 72시간 - 장기 주차 대응


class RedisPreRegistrationStore:
    def __init__(self, client: Redis):
        self.client = client

    def _key(self, lot_id: str, plate: str) -> str:
        return f"pre_reg:{lot_id}:{plate}"

    def save_pre_registration(self, *, lot_id: str, plate: str) -> dict:
        self.client.set(self._key(lot_id, plate), "1", ex=PRE_REG_TTL_SECONDS)
        return {"lot_id": lot_id, "plate": plate}

    def get_active_pre_registration(self, *, lot_id: str, plate: str) -> dict | None:
        exists = self.client.get(self._key(lot_id, plate))
        if not exists:
            return None
        return {"lot_id": lot_id, "plate": plate}

    def consume_pre_registration(self, *, lot_id: str, plate: str) -> None:
        self.client.delete(self._key(lot_id, plate))


class RedisParkingSessionStore:
    """주차 중인 차량의 실시간 상태를 관리한다. DB는 영구 이력 전용."""

    def __init__(self, client: Redis):
        self.client = client

    def _key(self, lot_id: str, plate: str) -> str:
        return f"parking_session:{lot_id}:{plate}"

    def save_session(self, *, lot_id: str, plate: str, pms_session_id: str, entry_time: str) -> None:
        payload = {
            "pms_session_id": pms_session_id,
            "lot_id": lot_id,
            "plate": plate,
            "entry_time": entry_time,
            "status": "active",
        }
        self.client.set(self._key(lot_id, plate), json.dumps(payload), ex=SESSION_TTL_SECONDS)

    def get_session(self, *, lot_id: str, plate: str) -> dict | None:
        raw = self.client.get(self._key(lot_id, plate))
        return json.loads(raw) if raw else None

    def update_status(self, *, lot_id: str, plate: str, status: str) -> None:
        key = self._key(lot_id, plate)
        raw = self.client.get(key)
        if raw is None:
            return
        payload = json.loads(raw)
        payload["status"] = status
        ttl = self.client.ttl(key)
        ex = ttl if ttl > 0 else SESSION_TTL_SECONDS
        self.client.set(key, json.dumps(payload), ex=ex)

    def delete_session(self, *, lot_id: str, plate: str) -> None:
        self.client.delete(self._key(lot_id, plate))
