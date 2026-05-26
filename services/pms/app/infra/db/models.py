"""
PMS DB Models (SQLAlchemy)
"""
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, Text, CheckConstraint,
    Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import uuid

Base = declarative_base()


class PMSParkingSession(Base):
    """PMS 기준 주차 세션 정보"""
    __tablename__ = 'parking_sessions'
    
    pms_session_id = Column(Text, primary_key=True)
    lot_id = Column(Text, nullable=False, default='mock_lot_001')
    plate = Column(String(20), nullable=False, default='')
    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(Text, nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    payment_requests = relationship('PaymentRequest', back_populates='parking_session')
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("status IN ('active', 'exited', 'cancelled')", name='ck_pms_parking_sessions_status'),
        Index('idx_pms_parking_sessions_plate', 'plate'),
        Index('idx_pms_parking_sessions_status', 'status'),
        Index('uniq_active_pms_session_per_plate', 'plate', unique=True, postgresql_where=text("status = 'active'")),
    )


class PaymentRequest(Base):
    """PMS가 Car Pay-in에 요청한 출차 결제 이력"""
    __tablename__ = 'payment_requests'
    
    payment_request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text('gen_random_uuid()'))
    pms_session_id = Column(Text, ForeignKey('parking_sessions.pms_session_id'), nullable=False)
    carpay_parking_session_id = Column(Text, nullable=True)  # Logical reference to Car Pay-in DB
    carpay_tx_id = Column(Text, nullable=True)  # Logical reference to Car Pay-in DB
    amount = Column(Integer, nullable=False)
    currency = Column(Text, nullable=False, default='KRW')
    status = Column(Text, nullable=False, default='pending')
    idempotency_key = Column(Text, unique=True, nullable=False)
    approval_no = Column(Text, nullable=True)
    failed_reason = Column(Text, nullable=True)
    requested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    parking_session = relationship('PMSParkingSession', back_populates='payment_requests')
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint('amount >= 0', name='ck_payment_requests_amount'),
        CheckConstraint("status IN ('pending', 'success', 'failed', 'cancelled')", name='ck_payment_requests_status'),
        Index('idx_payment_requests_pms_session_id', 'pms_session_id'),
        Index('idx_payment_requests_status', 'status'),
        Index('idx_payment_requests_carpay_parking_session_id', 'carpay_parking_session_id'),
        Index('idx_payment_requests_carpay_tx_id', 'carpay_tx_id'),
    )
