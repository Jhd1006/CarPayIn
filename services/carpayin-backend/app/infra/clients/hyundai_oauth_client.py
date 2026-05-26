"""
현대차 OAuth HTTP 클라이언트.

유닛 테스트의 FakeHyundaiOAuthClient와 동일한 인터페이스를 구현한다.
"""

import httpx


class HttpxHyundaiOAuthClient:
    """httpx 기반 현대차 OAuth HTTP 클라이언트."""

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
        """
        Args:
            token_url: 토큰 교환 엔드포인트 URL
            user_info_url: 사용자 정보 조회 엔드포인트 URL
            vehicle_list_url: 차량 목록 조회 엔드포인트 URL
            client_id: 현대차 OAuth 클라이언트 ID
            client_secret: 현대차 OAuth 클라이언트 시크릿
            redirect_uri: OAuth 콜백 redirect URI
            timeout: 요청 타임아웃(초)
        """
        self._token_url = token_url
        self._user_info_url = user_info_url
        self._vehicle_list_url = vehicle_list_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._timeout = timeout

    # ── UC-AUTH-003: OAuth code → token 교환 ─────────────────────────────

    def exchange_code(self, *, code: str, redirect_uri: str) -> dict:
        """
        Authorization code를 access token으로 교환한다.

        POST {token_url}

        Returns:
            {"access_token": str, "refresh_token": str}
        """
        try:
            response = httpx.post(
                self._token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"hyundai token api failed: {e}") from e

        data = response.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
        }

    # ── UC-AUTH-003: 사용자 프로필 조회 ──────────────────────────────────

    def get_user_profile(self, *, access_token: str) -> dict:
        """
        현대차 access token으로 사용자 프로필을 조회한다.

        GET {user_info_url}

        Returns:
            {"user_id": str, "name": str}
        """
        try:
            response = httpx.get(
                self._user_info_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"hyundai user profile api failed: {e}") from e

        data = response.json()
        return {
            "user_id": data["user_id"],
            "name": data["name"],
        }

    # ── UC-AUTH-003: 차량 목록 조회 ──────────────────────────────────────

    def get_vehicle_list(self, *, access_token: str) -> list[dict]:
        """
        현대차 access token으로 보유 차량 목록을 조회한다.

        GET {vehicle_list_url}

        Returns:
            [{"car_id": str, "vin": str, "model": str}, ...]
        """
        try:
            response = httpx.get(
                self._vehicle_list_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"hyundai vehicle list api failed: {e}") from e

        return response.json()
