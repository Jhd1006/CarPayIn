"""
서비스 헬스 체크 API 테스트.
GET /health
"""

from fastapi.testclient import TestClient

from app.main import app


class TestHealthApi:
    """GET /health"""

    def test_health_returns_200_with_ok_status(self):
        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
