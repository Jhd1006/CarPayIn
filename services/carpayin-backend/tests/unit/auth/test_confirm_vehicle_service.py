"""
UC-AUTH-005: 차량 선택 확정과 앱 토큰 발급 테스트

테스트 시나리오:
1. 유효한 car_id와 vin_hash면 차량을 저장하고 app token을 발급한다.
2. refresh token 원문은 DB에 저장하지 않는다 (hash만 저장).
3. 임시 토큰이 만료되면 예외를 발생시킨다.
4. 차량 목록에 없는 car_id면 예외를 발생시킨다.
5. vin_hash가 다르면 예외를 발생시킨다.
6. QR 세션이 만료되면 예외를 발생시킨다.
"""
import pytest
import hashlib
from datetime import datetime, timedelta
from typing import Optional


# ===========================================================================
# 공통 상수
# ===========================================================================

# 유효한 값들
VALID_TEMP_TOKEN = "temp_token_abc123"
VALID_CAR_ID = "HYUNDAI_CAR_001"
VALID_VIN_HASH = "vin_hash_xyz789"
VALID_USER_ID = "user_12345"
VALID_SESSION_ID = "session_67890"

# 차량 목록
VALID_CAR_LIST = ["HYUNDAI_CAR_001", "HYUNDAI_CAR_002"]

# 무효한 값들
INVALID_CAR_ID = "INVALID_CAR_999"
WRONG_VIN_HASH = "WRONG_VIN_HASH"
EXPIRED_TEMP_TOKEN = "expired_temp_token"


# ===========================================================================
# Domain 예외 (임시 - 나중에 app/domain/auth/errors.py로 이동)
# ===========================================================================

class CarIdNotInListError(Exception):
    """차량 목록에 없는 car_id"""
    pass


class VinHashMismatchError(Exception):
    """VIN hash 불일치"""
    pass


class TempTokenExpiredError(Exception):
    """임시 토큰 만료"""
    pass


class QRSessionExpiredError(Exception):
    """QR 세션 만료"""
    pass


# ===========================================================================
# Fake 구현체 (테스트용)
# ===========================================================================

class FakeVehicleRepository:
    """차량 Repository Fake - 메모리 저장"""
    
    def __init__(self):
        self.saved_vehicle = None
    
    def save(self, vehicle):
        """차량 저장"""
        self.saved_vehicle = vehicle
        return vehicle


class FakeRefreshTokenRepository:
    """Refresh Token Repository Fake - 메모리 저장"""
    
    def __init__(self):
        self.saved_token_hash = None
    
    def save(self, token_hash: str, user_id: str, car_id: str, expires_at: str):
        """Refresh token hash 저장 (원문 아님!)"""
        self.saved_token_hash = token_hash
        return token_hash


class FakeLoginCache:
    """로그인 캐시 Fake - Redis 대체"""
    
    def __init__(self):
        self.sessions = {}
        self.expired_tokens = set()
    
    def set_car_list(self, temp_token: str, car_list: list):
        """차량 목록 설정"""
        if temp_token not in self.sessions:
            self.sessions[temp_token] = {}
        self.sessions[temp_token]["car_list"] = car_list
    
    def set_expected_vin_hash(self, temp_token: str, vin_hash: str):
        """기대되는 VIN hash 설정"""
        if temp_token not in self.sessions:
            self.sessions[temp_token] = {}
        self.sessions[temp_token]["vin_hash"] = vin_hash
    
    def set_expired(self, temp_token: str):
        """토큰을 만료 상태로 설정"""
        self.expired_tokens.add(temp_token)
        if temp_token not in self.sessions:
            self.sessions[temp_token] = {}
    
    def clear(self):
        """모든 세션 삭제 (QR 세션 만료 시뮬레이션)"""
        self.sessions.clear()
    
    def get_session(self, temp_token: str) -> Optional[dict]:
        """세션 조회"""
        if temp_token in self.expired_tokens:
            return None
        return self.sessions.get(temp_token)
    
    def mark_complete(self, session_id: str):
        """세션을 완료 상태로 표시"""
        if session_id in self.sessions:
            self.sessions[session_id]["status"] = "complete"
    
    def is_complete(self, session_id: str) -> bool:
        """세션이 완료 상태인지 확인"""
        session = self.sessions.get(session_id)
        return session and session.get("status") == "complete"


class FakeConfirmVehicleService:
    """차량 확정 서비스 Fake - 실제 서비스 구현 전까지 사용"""
    
    def __init__(self, vehicle_repo, token_repo, login_cache):
        self.vehicle_repo = vehicle_repo
        self.token_repo = token_repo
        self.login_cache = login_cache
    
    def confirm_vehicle(self, temp_token: str, car_id: str, vin_hash: str):
        """차량 확정 및 앱 토큰 발급"""
        
        # 1. QR 세션 존재 여부 확인 (먼저!)
        if not self.login_cache.sessions:
            raise QRSessionExpiredError("QR 세션이 만료되었습니다")
        
        # 2. 임시 토큰 만료 체크
        session = self.login_cache.get_session(temp_token)
        if session is None:
            raise TempTokenExpiredError("임시 토큰이 만료되었습니다")
        
        # 3. 차량 목록 검증
        car_list = session.get("car_list", [])
        if car_id not in car_list:
            raise CarIdNotInListError(f"차량 목록에 없는 car_id: {car_id}")
        
        # 4. VIN hash 검증
        expected_vin_hash = session.get("vin_hash")
        if expected_vin_hash and vin_hash != expected_vin_hash:
            raise VinHashMismatchError("VIN hash가 일치하지 않습니다")
        
        # 5. Vehicle 저장
        vehicle = {
            "car_id": car_id,
            "vin_hash": vin_hash,
            "user_id": VALID_USER_ID
        }
        self.vehicle_repo.save(vehicle)
        
        # 6. 토큰 발급
        access_token = f"at_{car_id}_abc123"
        refresh_token = f"rt_{car_id}_xyz789"
        
        # 7. Refresh token hash 저장 (원문 저장 금지!)
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        self.token_repo.save(
            token_hash=token_hash,
            user_id=VALID_USER_ID,
            car_id=car_id,
            expires_at=(datetime.now() + timedelta(days=30)).isoformat()
        )
        
        # 8. Redis 세션 완료 처리 (temp_token 사용!)
        self.login_cache.mark_complete(temp_token)
        
        # 9. 결과 반환
        class Result:
            def __init__(self, access_token, refresh_token, user_id, car_id):
                self.access_token = access_token
                self.refresh_token = refresh_token
                self.user_id = user_id
                self.car_id = car_id
        
        return Result(access_token, refresh_token, VALID_USER_ID, car_id)


# ===========================================================================
# 테스트 케이스
# ===========================================================================

class TestConfirmVehicleService:
    """차량 확정 서비스 테스트"""
    
    def test_confirm_vehicle_success(self):
        """
        테스트 1: 유효한 car_id와 vin_hash면 차량을 저장하고 app token을 발급한다.
        """
        fake_vehicle_repo = FakeVehicleRepository()
        fake_token_repo = FakeRefreshTokenRepository()
        fake_login_cache = FakeLoginCache()
        
        # 테스트 데이터 설정
        fake_login_cache.set_car_list(VALID_TEMP_TOKEN, VALID_CAR_LIST)
        fake_login_cache.set_expected_vin_hash(VALID_TEMP_TOKEN, VALID_VIN_HASH)
        
        service = FakeConfirmVehicleService(
            vehicle_repo=fake_vehicle_repo,
            token_repo=fake_token_repo,
            login_cache=fake_login_cache
        )
        
        result = service.confirm_vehicle(VALID_TEMP_TOKEN, VALID_CAR_ID, VALID_VIN_HASH)
        
        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.user_id == VALID_USER_ID
        assert result.car_id == VALID_CAR_ID
        assert fake_vehicle_repo.saved_vehicle is not None
        assert fake_vehicle_repo.saved_vehicle["car_id"] == VALID_CAR_ID
        assert fake_token_repo.saved_token_hash is not None
        assert fake_login_cache.is_complete(VALID_TEMP_TOKEN) is True
    
    def test_refresh_token_stored_as_hash_only(self):
        """
        테스트 2: refresh token 원문은 DB에 저장하지 않는다 (hash만 저장)
        """
        fake_vehicle_repo = FakeVehicleRepository()
        fake_token_repo = FakeRefreshTokenRepository()
        fake_login_cache = FakeLoginCache()
        
        fake_login_cache.set_car_list(VALID_TEMP_TOKEN, VALID_CAR_LIST)
        fake_login_cache.set_expected_vin_hash(VALID_TEMP_TOKEN, VALID_VIN_HASH)
        
        service = FakeConfirmVehicleService(
            vehicle_repo=fake_vehicle_repo,
            token_repo=fake_token_repo,
            login_cache=fake_login_cache
        )
        
        result = service.confirm_vehicle(VALID_TEMP_TOKEN, VALID_CAR_ID, VALID_VIN_HASH)
        
        refresh_token = result.refresh_token
        saved_token_hash = fake_token_repo.saved_token_hash
        
        assert refresh_token != saved_token_hash
        assert len(saved_token_hash) == 64
    
    def test_temp_token_expired_raises_error(self):
        """
        테스트 3: 임시 토큰이 만료되면 예외를 발생시킨다.
        """
        fake_vehicle_repo = FakeVehicleRepository()
        fake_token_repo = FakeRefreshTokenRepository()
        fake_login_cache = FakeLoginCache()
        fake_login_cache.set_expired(EXPIRED_TEMP_TOKEN)
        
        service = FakeConfirmVehicleService(
            vehicle_repo=fake_vehicle_repo,
            token_repo=fake_token_repo,
            login_cache=fake_login_cache
        )
        
        with pytest.raises(TempTokenExpiredError):
            service.confirm_vehicle(EXPIRED_TEMP_TOKEN, VALID_CAR_ID, VALID_VIN_HASH)
        
        assert fake_vehicle_repo.saved_vehicle is None
        assert fake_token_repo.saved_token_hash is None
    
    def test_car_id_not_in_list_raises_error(self):
        """
        테스트 4: 차량 목록에 없는 car_id면 예외를 발생시킨다.
        """
        fake_vehicle_repo = FakeVehicleRepository()
        fake_token_repo = FakeRefreshTokenRepository()
        fake_login_cache = FakeLoginCache()
        fake_login_cache.set_car_list(VALID_TEMP_TOKEN, VALID_CAR_LIST)
        
        service = FakeConfirmVehicleService(
            vehicle_repo=fake_vehicle_repo,
            token_repo=fake_token_repo,
            login_cache=fake_login_cache
        )
        
        with pytest.raises(CarIdNotInListError):
            service.confirm_vehicle(VALID_TEMP_TOKEN, INVALID_CAR_ID, VALID_VIN_HASH)
        
        assert fake_vehicle_repo.saved_vehicle is None
        assert fake_token_repo.saved_token_hash is None
    
    def test_vin_hash_mismatch_raises_error(self):
        """
        테스트 5: vin_hash가 다르면 예외를 발생시킨다.
        """
        fake_vehicle_repo = FakeVehicleRepository()
        fake_token_repo = FakeRefreshTokenRepository()
        fake_login_cache = FakeLoginCache()
        fake_login_cache.set_car_list(VALID_TEMP_TOKEN, VALID_CAR_LIST)
        fake_login_cache.set_expected_vin_hash(VALID_TEMP_TOKEN, VALID_VIN_HASH)
        
        service = FakeConfirmVehicleService(
            vehicle_repo=fake_vehicle_repo,
            token_repo=fake_token_repo,
            login_cache=fake_login_cache
        )
        
        with pytest.raises(VinHashMismatchError):
            service.confirm_vehicle(VALID_TEMP_TOKEN, VALID_CAR_ID, WRONG_VIN_HASH)
        
        assert fake_vehicle_repo.saved_vehicle is None
        assert fake_token_repo.saved_token_hash is None
    
    def test_qr_session_expired_raises_error(self):
        """
        테스트 6: QR 세션이 만료되면 예외를 발생시킨다.
        """
        fake_vehicle_repo = FakeVehicleRepository()
        fake_token_repo = FakeRefreshTokenRepository()
        fake_login_cache = FakeLoginCache()
        fake_login_cache.clear()
        
        service = FakeConfirmVehicleService(
            vehicle_repo=fake_vehicle_repo,
            token_repo=fake_token_repo,
            login_cache=fake_login_cache
        )
        
        with pytest.raises(QRSessionExpiredError):
            service.confirm_vehicle(VALID_TEMP_TOKEN, VALID_CAR_ID, VALID_VIN_HASH)
        
        assert fake_vehicle_repo.saved_vehicle is None
        assert fake_token_repo.saved_token_hash is None