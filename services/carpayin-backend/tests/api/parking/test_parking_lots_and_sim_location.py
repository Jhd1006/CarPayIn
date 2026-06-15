from fastapi.testclient import TestClient

from app.main import app


def test_parking_lots_include_webots_test_lot():
    with TestClient(app) as client:
        response = client.get("/parking/lots")

    assert response.status_code == 200
    lots = response.json()["lots"]
    test_lot = next(lot for lot in lots if lot["id"] == "LOT_TEST_01")
    assert test_lot["name"] == "42dot 테스트 주차장"
    assert test_lot["lat"] == 37.48544722
    assert test_lot["lng"] == 127.03636666


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
