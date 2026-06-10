# pre_registrations 테이블 및 관련 repository 제거됨
# 사전등록은 Redis TTL 기반으로 관리한다.
# services/pms/app/infra/redis/stores.py RedisPreRegistrationStore 참고
# migration: 003_drop_pre_registrations
