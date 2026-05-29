import httpx

from app.infra.clients.pg_client import HttpxPgClient


def test_card_registration_url_uses_public_base_url():
    client = HttpxPgClient(
        "http://mock-pg:8000",
        public_base_url="http://10.0.2.2:8002",
    )

    assert (
        client.create_card_registration_url(order_id="order-001")
        == "http://10.0.2.2:8002/pg/card-register?order_id=order-001"
    )


def test_charge_billing_key_uses_internal_base_url(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return httpx.Response(
            200,
            json={"status": "success", "pg_tx_id": "tx-001", "approval_no": "ap-001"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = HttpxPgClient(
        "http://mock-pg:8000",
        public_base_url="http://10.0.2.2:8002",
    )

    assert client.charge_billing_key(
        billing_key="bk-001",
        amount=1000,
        currency="KRW",
        idempotency_key="idem-001",
    ) == {"success": True, "pg_tx_id": "tx-001", "approval_no": "ap-001"}
    assert calls[0]["url"] == "http://mock-pg:8000/pg/payments/billing"
