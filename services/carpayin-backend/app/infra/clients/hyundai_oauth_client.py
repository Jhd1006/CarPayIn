import httpx


def _safe_keys(data) -> list[str]:
    if not isinstance(data, dict):
        return []

    keys = set(data.keys())
    for value in data.values():
        if isinstance(value, dict):
            keys.update(value.keys())
    return sorted(str(key) for key in keys)


def _dict_candidates(data):
    if not isinstance(data, dict):
        return

    yield data
    for key in ("data", "result", "profile", "user", "userInfo", "body"):
        value = data.get(key)
        if isinstance(value, dict):
            yield value


def _pick_text(data, keys: tuple[str, ...], error_code: str) -> str:
    for candidate in _dict_candidates(data):
        for key in keys:
            value = candidate.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()

    raise RuntimeError(f"{error_code}: response keys={_safe_keys(data)}")


def _extract_list(data) -> list:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for key in ("cars", "vehicles", "carList", "carlist", "data", "result", "list"):
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_list(value)
            if nested:
                return nested
    return []


def _normalize_vehicle(item) -> dict:
    if not isinstance(item, dict):
        return {}

    car_id = (
        item.get("car_id")
        or item.get("carId")
        or item.get("carID")
        or item.get("vehicle_id")
        or item.get("vehicleId")
    )
    car_sellname = (
        item.get("car_sellname")
        or item.get("carSellname")
        or item.get("carSellName")
        or item.get("model")
        or item.get("modelName")
        or item.get("carName")
        or ""
    )
    plate = (
        item.get("plate")
        or item.get("plate_number")
        or item.get("plateNumber")
        or item.get("carRegNo")
        or item.get("carNo")
        or ""
    )

    normalized = dict(item)
    if car_id is not None:
        normalized["car_id"] = str(car_id)
    normalized["car_sellname"] = str(car_sellname)
    normalized["plate"] = str(plate)
    return normalized


class HttpxHyundaiOAuthClient:
    """HTTP client for Hyundai OAuth/account/data APIs."""

    def __init__(
        self,
        token_url: str,
        user_info_url: str,
        vehicle_list_url: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        timeout: float = 10.0,
    ):
        self._token_url = token_url
        self._user_info_url = user_info_url
        self._vehicle_list_url = vehicle_list_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._timeout = timeout

    def exchange_code(self, *, code: str, redirect_uri: str) -> dict:
        try:
            response = httpx.post(
                self._token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                auth=(self._client_id, self._client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"hyundai token api failed: {exc}") from exc

        data = response.json()
        return {
            "access_token": _pick_text(
                data,
                ("access_token", "accessToken"),
                "hyundai token response missing access_token",
            ),
            "refresh_token": _pick_text(
                data,
                ("refresh_token", "refreshToken"),
                "hyundai token response missing refresh_token",
            ),
        }

    def get_user_profile(self, *, access_token: str) -> dict:
        try:
            response = httpx.get(
                self._user_info_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"hyundai user profile api failed: {exc}") from exc

        data = response.json()
        return {
            "user_id": _pick_text(
                data,
                ("user_id", "userId", "useId", "id", "sub", "accountId"),
                "hyundai profile response missing user_id",
            ),
            "name": _pick_text(
                data,
                ("name", "userName", "username", "displayName", "nickName", "email"),
                "hyundai profile response missing name",
            ),
        }

    def get_vehicle_list(self, *, access_token: str) -> list[dict]:
        try:
            response = httpx.get(
                self._vehicle_list_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"hyundai vehicle list api failed: {exc}") from exc

        data = response.json()
        return [
            car
            for car in (_normalize_vehicle(item) for item in _extract_list(data))
            if car.get("car_id")
        ]
