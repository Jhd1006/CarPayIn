from app.infra.clients.molit_client import LocalMolitBypassClient


def test_local_molit_bypass_approves_owner_check():
    client = LocalMolitBypassClient()

    assert client.verify_owner(
        plate="12가3456",
        user_id="user-001",
        car_id="car-001",
    )
