import sys
sys.path.insert(0, ".")
from app.infra.security import SignedTokenCodec

codec = SignedTokenCodec("carpayin-dev-token-secret")
token = codec.issue(token_type="app_access", ttl_seconds=3600, user_id="test-user-001", car_id="test-car-001")
# 토큰만 출력 (다른 텍스트 없음)
print(token, end="")
