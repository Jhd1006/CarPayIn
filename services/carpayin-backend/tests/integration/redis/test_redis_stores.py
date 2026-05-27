import os
from uuid import uuid4

import pytest
from redis import Redis

from app.infra.redis.stores import (
    RedisAppLoginResultStore,
    RedisCardOrderStore,
    RedisFeeQuoteStore,
    RedisHyundaiAccessTokenStore,
    RedisHyundaiOAuthResultStore,
    RedisOAuthStateStore,
    RedisPreNotifyStore,
    RedisQrSessionStore,
)


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture
def redis_client():
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    client.ping()
    yield client
    client.close()


def assert_ttl(client: Redis, key: str, expected_seconds: int) -> None:
    ttl_seconds = client.ttl(key)
    assert 0 < ttl_seconds <= expected_seconds


def test_auth_redis_stores_persist_status_and_ttl(redis_client):
    unique_id = uuid4().hex
    session_id = f"session-{unique_id}"
    oauth_state = f"state-{unique_id}"
    user_id = f"user-{unique_id}"
    qr_key = f"qr_session:{session_id}"
    state_key = f"oauth_state:{oauth_state}"
    access_key = f"hyundai_access:{user_id}"
    oauth_result_key = f"hyundai_oauth:{session_id}"
    login_result_key = f"app_login_result:{session_id}"

    qr_store = RedisQrSessionStore(redis_client)
    state_store = RedisOAuthStateStore(redis_client)
    access_store = RedisHyundaiAccessTokenStore(redis_client)
    oauth_result_store = RedisHyundaiOAuthResultStore(redis_client)
    login_result_store = RedisAppLoginResultStore(redis_client)

    try:
        qr_store.save_pending_session(
            session_id=session_id, vin_hash="vin-hash", ttl_seconds=900
        )
        assert qr_store.get_session(session_id)["status"] == "pending"
        assert_ttl(redis_client, qr_key, 900)

        qr_store.mark_failed(session_id=session_id, reason="oauth_failed")
        assert qr_store.get_session(session_id)["status"] == "failed"
        assert qr_store.get_session(session_id)["debug_message"] == "oauth_failed"

        state_store.save_oauth_state(
            oauth_state=oauth_state, session_id=session_id, ttl_seconds=900
        )
        assert state_store.get_session_id(oauth_state) == session_id
        assert_ttl(redis_client, state_key, 900)
        state_store.mark_used(oauth_state)
        assert state_store.get_session_id(oauth_state) is None

        access_store.save_access_token(
            user_id=user_id, access_token="hyundai-access-token", ttl_seconds=3600
        )
        assert (
            access_store.get_access_token(user_id)["hyundai_access_token"]
            == "hyundai-access-token"
        )
        assert_ttl(redis_client, access_key, 3600)

        cars = [{"car_id": "car-001", "plate": "12TEST34"}]
        oauth_result_store.save_result(
            session_id=session_id,
            user_id=user_id,
            name="Redis Test",
            cars=cars,
            temp_access_token="temporary-token",
            ttl_seconds=900,
        )
        assert oauth_result_store.get_result(session_id)["cars"] == cars
        assert_ttl(redis_client, oauth_result_key, 900)

        login_result_store.save_result(
            session_id=session_id,
            status="complete",
            user_id=user_id,
            name="Redis Test",
            cars=cars,
            temp_access_token="temporary-token",
            ttl_seconds=300,
        )
        assert login_result_store.get_result(session_id)["status"] == "complete"
        assert_ttl(redis_client, login_result_key, 300)
        login_result_store.mark_used(session_id)
        assert login_result_store.get_result(session_id) is None
    finally:
        redis_client.delete(
            qr_key,
            state_key,
            access_key,
            oauth_result_key,
            login_result_key,
        )


def test_card_parking_and_fee_redis_stores_persist_lifecycle(redis_client):
    unique_id = uuid4().hex
    order_id = f"order-{unique_id}"
    user_id = f"user-{unique_id}"
    car_id = f"car-{unique_id}"
    lot_id = f"lot-{unique_id}"
    plate = f"P{unique_id[:7]}"
    session_id = f"parking-{unique_id}"
    order_key = f"mock_pg_card_register:{order_id}"
    pre_notify_key = f"parking_pre_notify:{lot_id}:{plate}"
    quote_key = f"parking_fee_quote:{session_id}"

    card_store = RedisCardOrderStore(redis_client)
    pre_notify_store = RedisPreNotifyStore(redis_client)
    quote_store = RedisFeeQuoteStore(redis_client)

    try:
        card_store.save_pending(
            order_id=order_id,
            user_id=user_id,
            car_id=car_id,
            ttl_seconds=1800,
        )
        assert card_store.get_pending(order_id=order_id)["car_id"] == car_id
        assert_ttl(redis_client, order_key, 1800)
        card_store.mark_complete(order_id=order_id)
        assert card_store.get_pending(order_id=order_id) is None
        assert card_store.get_order(order_id=order_id)["status"] == "complete"

        pre_notify_store.save_incoming(
            lot_id=lot_id,
            plate=plate,
            car_id=car_id,
            user_id=user_id,
            ttl_seconds=3600,
        )
        assert pre_notify_store.get_pre_notify(lot_id, plate)["status"] == "incoming"
        assert_ttl(redis_client, pre_notify_key, 3600)
        pre_notify_store.delete_pre_notify(lot_id, plate)
        assert pre_notify_store.get_pre_notify(lot_id, plate) is None

        quote_store.save_quote(
            session_id=session_id,
            lot_id=lot_id,
            amount=5000,
            duration=90,
            currency="KRW",
            entry_time="2026-05-27T10:00:00+09:00",
            ttl_seconds=300,
        )
        assert quote_store.get_quote(session_id)["amount"] == 5000
        assert quote_store.get_quote(session_id)["duration"] == 90
        assert_ttl(redis_client, quote_key, 300)
    finally:
        redis_client.delete(order_key, pre_notify_key, quote_key)
