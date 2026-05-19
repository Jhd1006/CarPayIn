"""
UC-AUTH-006: 앱 access token 재발급 테스트

테스트 시나리오:
1. active refresh token이면 새 access token을 반환한다.
2. 만료된 token이면 401을 반환하고 expired로 표시한다.
3. 원문 refresh token은 저장하지 않는다 (hash만 저장).
"""
import pytest
import hashlib
from datetime import datetime, timedelta
from typing import Optional


# ===========================================================================
# 공통 상수
# ===========================================================================

# 유효한 값들
VALID_REFRESH_TOKEN = "rt_valid_abc123xyz"
VALID_USER_ID = "user_12345"
VALID_CAR_ID = "HYUNDAI_CAR_001"

# 무효한 값들
EXPIRED_REFRESH_TOKEN = "rt_expired_xyz789"
REVOKED_REFRESH_TOKEN = "rt_revoked_abc789"
NONEXISTENT_REFRESH_TOKEN = "rt_nonexistent_000"


# ===========================================================================
# Domain 예외 (임시 - 나중에 app/domain/auth/errors.py로 이동)
# ===========================================================================

class RefreshTokenNotFoundError(Exception):
    """Refresh token이 DB에 없음"""
    pass


class RefreshTokenExpiredError(Exception):
    """Refresh token 만료"""
    pass


class RefreshTokenRevokedError(Exception):
    """Refresh token이 revoked 상태"""
    pass


# ===========================================================================
# Fake 구현체 (테스트용)
# ===========================================================================

class FakeRefreshTokenRepository:
    """Refresh Token Repository Fake - 메모리 저장"""
    
    def __init__(self):
        self.tokens = {}  # {token_hash: {status, user_id, car_id, expires_at}}
    
    def save(self, token_hash: str, user_id: str, car_id: str, expires_at: str, status: str = "active"):
        """Refresh token 저장 (hash만!)"""
        self.tokens[token_hash] = {
            "status": status,
            "user_id": user_id,
            "car_id": car_id,
            "expires_at": expires_at
        }
    
    def find_by_hash(self, token_hash: str) -> Optional[dict]:
        """Hash로 토큰 조회"""
        return self.tokens.get(token_hash)
    
    def update_status(self, token_hash: str, status: str):
        """토큰 상태 변경"""
        if token_hash in self.tokens:
            self.tokens[token_hash]["status"] = status


class FakeRefreshTokenService:
    """Refresh Token 서비스 Fake - 실제 서비스 구현 전까지 사용"""
    
    def __init__(self, token_repo):
        self.token_repo = token_repo
    
    def refresh_access_token(self, refresh_token: str):
        """Refresh token으로 새 access token 발급"""
        
        # 1. Refresh token hash 계산
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        
        # 2. DB에서 token 조회
        token_record = self.token_repo.find_by_hash(token_hash)
        if token_record is None:
            raise RefreshTokenNotFoundError("Refresh token이 존재하지 않습니다")
        
        # 3. 상태 확인
        if token_record["status"] == "revoked":
            raise RefreshTokenRevokedError("Refresh token이 revoked 상태입니다")
        
        # 4. 만료 확인
        expires_at = token_record["expires_at"]
        if datetime.now().isoformat() > expires_at:
            # 만료된 경우 상태 업데이트
            self.token_repo.update_status(token_hash, "expired")
            raise RefreshTokenExpiredError("Refresh token이 만료되었습니다")
        
        # 5. 유효하면 새 access token 발급
        user_id = token_record["user_id"]
        car_id = token_record["car_id"]
        new_access_token = f"at_{car_id}_new_{datetime.now().timestamp()}"
        
        # 6. 결과 반환
        class Result:
            def __init__(self, access_token, user_id, car_id):
                self.access_token = access_token
                self.user_id = user_id
                self.car_id = car_id
        
        return Result(new_access_token, user_id, car_id)


# ===========================================================================
# 테스트 케이스
# ===========================================================================

class TestRefreshTokenService:
    """Refresh token 서비스 테스트"""
    
    def test_active_refresh_token_returns_new_access_token(self):
        """
        테스트 1: active refresh token이면 새 access token을 반환한다.
        """
        fake_token_repo = FakeRefreshTokenRepository()
        
        # Active refresh token 저장 (hash로!)
        token_hash = hashlib.sha256(VALID_REFRESH_TOKEN.encode()).hexdigest()
        fake_token_repo.save(
            token_hash=token_hash,
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            expires_at=(datetime.now() + timedelta(days=30)).isoformat(),
            status="active"
        )
        
        service = FakeRefreshTokenService(token_repo=fake_token_repo)
        
        result = service.refresh_access_token(VALID_REFRESH_TOKEN)
        
        assert result.access_token is not None
        assert result.user_id == VALID_USER_ID
        assert result.car_id == VALID_CAR_ID
    
    def test_expired_token_raises_error(self):
        """
        테스트 2: 만료된 token이면 예외를 반환하고, expired표시
        """
        fake_token_repo = FakeRefreshTokenRepository()
        
        # 만료된 refresh token 저장
        token_hash = hashlib.sha256(EXPIRED_REFRESH_TOKEN.encode()).hexdigest()
        fake_token_repo.save(
            token_hash=token_hash,
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            expires_at=(datetime.now() - timedelta(days=1)).isoformat(),  # 이미 만료
            status="active"
        )
        
        service = FakeRefreshTokenService(token_repo=fake_token_repo)
        
        with pytest.raises(RefreshTokenExpiredError):
            service.refresh_access_token(EXPIRED_REFRESH_TOKEN)
        
        # 상태가 expired로 변경되었는지 확인
        updated_token = fake_token_repo.find_by_hash(token_hash)
        assert updated_token["status"] == "expired"
    
    def test_refresh_token_stored_as_hash_only(self):
        """
        테스트 3: 원문 refresh token은 저장하지 않는다 (hash만 저장).
        """
        fake_token_repo = FakeRefreshTokenRepository()
        
        # Refresh token 원문
        refresh_token = VALID_REFRESH_TOKEN
        
        # Hash 계산
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        
        # 저장 (hash만!)
        fake_token_repo.save(
            token_hash=token_hash,
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            expires_at=(datetime.now() + timedelta(days=30)).isoformat(),
            status="active"
        )
        
        # 원문으로 조회하면 없어야 함
        found_by_plaintext = fake_token_repo.find_by_hash(refresh_token)
        assert found_by_plaintext is None
        
        # Hash로 조회하면 있어야 함
        found_by_hash = fake_token_repo.find_by_hash(token_hash)
        assert found_by_hash is not None
        
        # 원문과 hash가 달라야 함
        assert refresh_token != token_hash
        assert len(token_hash) == 64  # SHA-256
    
    def test_nonexistent_token_raises_error(self):
        """
        추가 테스트: 존재하지 않는 token이면 예외를 발생시킨다.
        """
        fake_token_repo = FakeRefreshTokenRepository()
        service = FakeRefreshTokenService(token_repo=fake_token_repo)
        
        with pytest.raises(RefreshTokenNotFoundError):
            service.refresh_access_token(NONEXISTENT_REFRESH_TOKEN)
    
    def test_revoked_token_raises_error(self):
        """
        추가 테스트: revoked 상태 token이면 예외를 발생시킨다.
        """
        fake_token_repo = FakeRefreshTokenRepository()
        
        # Revoked token 저장
        token_hash = hashlib.sha256(REVOKED_REFRESH_TOKEN.encode()).hexdigest()
        fake_token_repo.save(
            token_hash=token_hash,
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            expires_at=(datetime.now() + timedelta(days=30)).isoformat(),
            status="revoked"
        )
        
        service = FakeRefreshTokenService(token_repo=fake_token_repo)
        
        with pytest.raises(RefreshTokenRevokedError):
            service.refresh_access_token(REVOKED_REFRESH_TOKEN)