from fastapi.testclient import TestClient

from app.main import app


def test_parking_lots_returns_partner_lots():
    with TestClient(app) as client:
        response = client.get("/parking/lots")

    assert response.status_code == 200
    lots = response.json()["lots"]
    lot_ids = [lot["id"] for lot in lots]
    assert "LOT_GANGNAM_01" in lot_ids
    assert "LOT_TEST_01" not in lot_ids


def test_sim_location_can_be_updated_and_read_back():
    payload = {
        "lat": 37.493123,
        "lng": 127.049812,
        "speed_kph": 18.0,
        "source": "webots-test",
    }

    with TestClient(app) as client:
        update_response = client.post("/sim/location", json=payload)
        read_response = client.get("/sim/location")

    assert update_response.status_code == 200
    assert read_response.status_code == 200
    body = read_response.json()
    assert body["lat"] == payload["lat"]
    assert body["lng"] == payload["lng"]
    assert body["speed_kph"] == payload["speed_kph"]
    assert body["source"] == payload["source"]
    assert body["updated_at"]
