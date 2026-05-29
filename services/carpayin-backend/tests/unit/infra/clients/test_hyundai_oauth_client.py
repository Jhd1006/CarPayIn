import httpx

from app.infra.clients.hyundai_oauth_client import HttpxHyundaiOAuthClient


def make_response(url: str, payload):
    return httpx.Response(200, json=payload, request=httpx.Request("GET", url))


def make_client() -> HttpxHyundaiOAuthClient:
    return HttpxHyundaiOAuthClient(
        token_url="https://hyundai.test/token",
        user_info_url="https://hyundai.test/profile",
        vehicle_list_url="https://hyundai.test/carlist",
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://app.test/auth/redirect",
    )


def test_exchange_code_uses_basic_auth_and_accepts_camel_case_tokens(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return make_response(
            url,
            {
                "accessToken": "access-001",
                "refreshToken": "refresh-001",
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = make_client().exchange_code(
        code="code-001",
        redirect_uri="https://app.test/auth/redirect",
    )

    assert result == {
        "access_token": "access-001",
        "refresh_token": "refresh-001",
    }
    assert calls[0]["auth"] == ("client-id", "client-secret")
    assert "client_id" not in calls[0]["data"]
    assert "client_secret" not in calls[0]["data"]


def test_get_user_profile_accepts_nested_hyundai_field_names(monkeypatch):
    def fake_get(url, **kwargs):
        return make_response(
            url,
            {
                "data": {
                    "userId": "hyundai-user-001",
                    "userName": "Hong Gil Dong",
                }
            },
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    assert make_client().get_user_profile(access_token="access-001") == {
        "user_id": "hyundai-user-001",
        "name": "Hong Gil Dong",
    }


def test_get_vehicle_list_normalizes_hyundai_car_list(monkeypatch):
    def fake_get(url, **kwargs):
        return make_response(
            url,
            {
                "data": [
                    {
                        "carId": "car-001",
                        "carSellname": "IONIQ 5",
                        "carRegNo": "12가3456",
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    assert make_client().get_vehicle_list(access_token="access-001") == [
        {
            "carId": "car-001",
            "carSellname": "IONIQ 5",
            "carRegNo": "12가3456",
            "car_id": "car-001",
            "car_sellname": "IONIQ 5",
            "plate": "12가3456",
        }
    ]
