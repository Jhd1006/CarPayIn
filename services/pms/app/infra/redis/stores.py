from redis import Redis

PRE_REG_TTL_SECONDS = 60 * 60  # 1시간 - 사전등록 후 차가 안 오면 자동 만료


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
