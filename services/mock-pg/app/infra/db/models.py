"""
Mock PG DB Models (SQLAlchemy)
"""
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, Text, CheckConstraint,
    Index, CHAR
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class BillingKey(Base):
    """카드 등록 성공 후 Mock PG가 발급하는 빌링키"""
    __tablename__ = 'billing_keys'
    
    billing_key = Column(Text, primary_key=True)
    order_id = Column(Text, unique=True, nullable=False)
    card_token = Column(Text, nullable=False)  # Logical reference to Mock Card DB
    card_last_four = Column(CHAR(4), default='')
    status = Column(Text, nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    transactions = relationship('PGTransaction', back_populates='billing_key_rel')
    
    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive')", name='ck_billing_keys_status'),
    )


class PGTransaction(Base):
    """Mock PG 기준 결제 요청/승인/실패 이력"""
    __tablename__ = 'transactions'
    
    pg_tx_id = Column(Text, primary_key=True)
    billing_key = Column(Text, ForeignKey('billing_keys.billing_key'), nullable=False)
    card_token = Column(Text, nullable=False)  # Logical reference to Mock Card DB
    card_tx_id = Column(Text, nullable=True)  # Logical reference to Mock Card DB tx.tx_id
    amount = Column(Integer, nullable=False)
    currency = Column(Text, nullable=False, default='KRW')
    approval_no = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default='pending')
    idempotency_key = Column(Text, unique=True, nullable=False)
    failed_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    billing_key_rel = relationship('BillingKey', back_populates='transactions')
    
    # Constraints
    __table_args__ = (
        CheckConstraint('amount > 0', name='ck_pg_transactions_amount'),
        CheckConstraint("status IN ('pending', 'success', 'failed', 'cancelled')", name='ck_pg_transactions_status'),
    )
