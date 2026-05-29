"""
MOLIT(국토교통부) 자동차 소유자 확인 HTTP 클라이언트.

유닛 테스트의 FakeMolitClient와 동일한 인터페이스를 구현한다.
"""

import httpx


class LocalMolitBypassClient:
    def verify_owner(self, *, plate: str, user_id: str, car_id: str) -> bool:
        return True


class HttpxMolitClient:
    """httpx 기반 국토교통부 자동차 소유자 확인 HTTP 클라이언트."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0):
        """
        Args:
            base_url: MOLIT API base URL
            api_key: MOLIT API 인증 키
            timeout: 요청 타임아웃(초)
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    # ── UC-CARD-001: 차량 소유자 확인 ────────────────────────────────────

    def verify_owner(self, *, plate: str, user_id: str, car_id: str) -> bool:
        """
        차량 번호판과 사용자 정보로 소유자 여부를 확인한다.

        POST {base_url}/verify/owner

        Returns:
            True: 소유자 확인 성공
            False: 소유자 불일치
        """
        try:
            response = httpx.post(
                f"{self._base_url}/verify/owner",
                json={
                    "plate": plate,
                    "user_id": user_id,
                    "car_id": car_id,
                },
                headers={"X-API-Key": self._api_key},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"molit_verification_failed: {e}") from e

        data = response.json()
        return data.get("verified", False)
