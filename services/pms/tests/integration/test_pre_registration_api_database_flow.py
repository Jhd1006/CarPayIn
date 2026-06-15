from uuid import uuid4

from fastapi.testclient import TestClient

from app.infra.redis import redis_client
from app.main import app


def test_pre_register_api_saves_plate_to_redis():
    unique_id = uuid4().hex
    lot_id = f"lot-api-{unique_id}"
    plate = f"A{unique_id[:7]}"
    key = f"pre_reg:{lot_id}:{plate}"

    try:
        with TestClient(app) as client:
            first_response = client.post(
                "/parking/pre-register",
                json={"lot_id": lot_id, "plate": plate},
            )
            second_response = client.post(
                "/parking/pre-register",
                json={"lot_id": lot_id, "plate": plate},
            )

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert first_response.json()["status"] == "registered"

        assert redis_client.get(key) == "1"
        ttl = redis_client.ttl(key)
        assert ttl > 0
    finally:
        redis_client.delete(key)
