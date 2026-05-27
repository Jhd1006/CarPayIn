"""
Car Pay-in Backend DB Models (SQLAlchemy)
"""
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, Text, CheckConstraint,
    Index, UniqueConstraint, CHAR
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func, text
import uuid

Base = declarative_base()


class User(Base):
    """현대 로그인 기준 사용자"""
    __tablename__ = 'users'
    
    user_id = Column(Text, primary_key=True)
    name = Column(Text, default='')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    vehicles = relationship('Vehicle', back_populates='user')
    app_refresh_tokens = relationship('AppRefreshToken', back_populates='user')
    hyundai_token = relationship('HyundaiToken', back_populates='user', uselist=False)


class Vehicle(Base):
    """사용자에게 등록된 차량"""
    __tablename__ = 'vehicles'
    
    car_id = Column(Text, primary_key=True)
    user_id = Column(Text, ForeignKey('users.user_id'), nullable=False)
    car_sellname = Column(Text, nullable=False, default='')
    plate = Column(String(20), nullable=False, default='')
    registered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship('User', back_populates='vehicles')
    billing_key = relationship('VehicleBillingKey', back_populates='vehicle', uselist=False)
    parking_sessions = relationship('ParkingSession', back_populates='vehicle')
    transactions = relationship('Transaction', back_populates='vehicle')
    app_refresh_tokens = relationship('AppRefreshToken', back_populates='vehicle')
    
    # Indexes
    __table_args__ = (
        Index('idx_vehicles_user_id', 'user_id'),
        Index('idx_vehicles_plate', 'plate', unique=True, postgresql_where=text("plate <> ''")),
    )


class VehicleBillingKey(Base):
    """차량과 PG 빌링키의 현재 매핑 (차량당 1개)"""
    __tablename__ = 'vehicle_billing_keys'
    
    car_id = Column(Text, ForeignKey('vehicles.car_id'), primary_key=True)
    billing_key = Column(Text, unique=True, nullable=False)
    card_last_four = Column(CHAR(4), nullable=False)
    status = Column(Text, nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    vehicle = relationship('Vehicle', back_populates='billing_key')
    
    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive')", name='ck_vehicle_billing_keys_status'),
        CheckConstraint("card_last_four ~ '^[0-9]{4}$'", name='ck_vehicle_billing_keys_card_last_four'),
    )


class ParkingSession(Base):
    """차량의 주차 세션 정보"""
    __tablename__ = 'parking_sessions'
    
    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text('gen_random_uuid()'))
    pms_session_id = Column(Text, nullable=True)
    car_id = Column(Text, ForeignKey('vehicles.car_id'), nullable=False)
    lot_id = Column(Text, nullable=False)
    plate = Column(String(20), nullable=False)
    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(Text, nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    vehicle = relationship('Vehicle', back_populates='parking_sessions')
    transactions = relationship('Transaction', back_populates='parking_session')
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'cancelled')", name='ck_parking_sessions_status'),
        Index('idx_parking_sessions_car_id', 'car_id'),
        Index('idx_parking_sessions_status', 'status'),
        Index('idx_parking_sessions_pms_session_id', 'pms_session_id'),
        Index('uniq_active_session_per_car', 'car_id', unique=True, postgresql_where=text("status = 'active'")),
        Index('uniq_parking_sessions_lot_pms', 'lot_id', 'pms_session_id', unique=True, postgresql_where=text('pms_session_id IS NOT NULL')),
    )


class Transaction(Base):
    """Car Pay-in 기준 결제 이력"""
    __tablename__ = 'transactions'
    
    tx_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text('gen_random_uuid()'))
    session_id = Column(UUID(as_uuid=True), ForeignKey('parking_sessions.session_id'), nullable=False)
    car_id = Column(Text, ForeignKey('vehicles.car_id'), nullable=False)
    billing_key = Column(Text, nullable=False)
    pg_tx_id = Column(Text, nullable=True)
    amount = Column(Integer, nullable=False)
    currency = Column(CHAR(3), nullable=False, default='KRW')
    status = Column(Text, nullable=False, default='pending')
    approval_no = Column(Text, nullable=True)
    idempotency_key = Column(Text, unique=True, nullable=False)
    failed_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    parking_session = relationship('ParkingSession', back_populates='transactions')
    vehicle = relationship('Vehicle', back_populates='transactions')
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint('amount > 0', name='ck_transactions_amount'),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name='ck_transactions_currency'),
        CheckConstraint("status IN ('pending', 'success', 'failed', 'cancelled')", name='ck_transactions_status'),
        Index('idx_transactions_session_id', 'session_id'),
        Index('idx_transactions_car_id', 'car_id'),
        Index('idx_transactions_billing_key', 'billing_key'),
        Index('idx_transactions_pg_tx_id', 'pg_tx_id'),
    )


class AppRefreshToken(Base):
    """AAOS 앱 refresh token (hash 값만 저장)"""
    __tablename__ = 'app_refresh_tokens'
    
    refresh_token_hash = Column(CHAR(64), primary_key=True)
    user_id = Column(Text, ForeignKey('users.user_id'), nullable=False)
    car_id = Column(Text, ForeignKey('vehicles.car_id'), nullable=False)
    status = Column(Text, nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship('User', back_populates='app_refresh_tokens')
    vehicle = relationship('Vehicle', back_populates='app_refresh_tokens')
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("status IN ('active', 'revoked', 'expired')", name='ck_app_refresh_tokens_status'),
        CheckConstraint("refresh_token_hash ~ '^[a-f0-9]{64}$'", name='ck_app_refresh_tokens_hash'),
        Index('idx_app_refresh_tokens_user_id', 'user_id'),
        Index('idx_app_refresh_tokens_car_id', 'car_id'),
        Index('idx_app_refresh_tokens_expires_at', 'expires_at'),
    )


class HyundaiToken(Base):
    """현대 API refresh token (암호화 저장, access token은 Redis)"""
    __tablename__ = 'hyundai_tokens'
    
    user_id = Column(Text, ForeignKey('users.user_id'), primary_key=True)
    hyundai_refresh_token_encrypted = Column(Text, nullable=False)
    refresh_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship('User', back_populates='hyundai_token')
