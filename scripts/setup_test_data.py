import sys
sys.path.insert(0, ".")
from app.infra.security import SignedTokenCodec
from sqlalchemy import create_engine, text
import os

db_url = os.environ.get("DATABASE_URL", "postgresql+psycopg://dev_user:dev_pass@carpayin-postgres:5432/carpayin_dev")
engine = create_engine(db_url)

with engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO users (user_id, name)
        VALUES ('test-user-001', 'Test User')
        ON CONFLICT (user_id) DO NOTHING
    """))
    conn.execute(text("""
        INSERT INTO vehicles (user_id, car_id, car_sellname, plate)
        VALUES ('test-user-001', 'test-car-001', '아이오닉6', '12가3456')
        ON CONFLICT (car_id) DO NOTHING
    """))
    conn.execute(text("""
        INSERT INTO vehicle_billing_keys (car_id, billing_key, card_last_four, status)
        VALUES ('test-car-001', 'mock-billing-key-001', '1234', 'active')
        ON CONFLICT (car_id) DO UPDATE SET billing_key=EXCLUDED.billing_key, status='active'
    """))
    print("DB 데이터 삽입 완료")

codec = SignedTokenCodec("carpayin-dev-token-secret")
token = codec.issue(token_type="app_access", ttl_seconds=3600, user_id="test-user-001", car_id="test-car-001")
print(f"TOKEN:{token}")
