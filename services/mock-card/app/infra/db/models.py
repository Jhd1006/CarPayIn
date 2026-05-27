"""
Mock Card DB Models (SQLAlchemy)
"""
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, Text, CheckConstraint,
    Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func, text
import uuid

Base = declarative_base()


class User(Base):
    """Mock 카드사 기준 사용자"""
    __tablename__ = 'users'
    
    user_id = Column(Text, primary_key=True)
    name = Column(Text, default='')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    cards = relationship('Card', back_populates='user')


class Card(Base):
    """Mock 카드사에 등록된 실제 카드 정보"""
    __tablename__ = 'cards'
    
    card_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text('gen_random_uuid()'))
    user_id = Column(Text, ForeignKey('users.user_id'), nullable=False)
    encrypted_card_num = Column(Text, nullable=False)
    cvc_hmac = Column(Text, nullable=True)
    exp_month = Column(Integer, nullable=False)
    exp_year = Column(Integer, nullable=False)
    status = Column(Text, nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship('User', back_populates='cards')
    card_tokens = relationship('CardToken', back_populates='card')
    
    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint('user_id', 'encrypted_card_num', name='uq_cards_user_encrypted_card_num'),
        CheckConstraint('exp_month BETWEEN 1 AND 12', name='ck_cards_exp_month'),
        CheckConstraint("status IN ('active', 'inactive', 'expired')", name='ck_cards_status'),
    )


class CardToken(Base):
    """PG/결제 승인 요청에서 사용할 카드 토큰"""
    __tablename__ = 'card_tokens'
    
    card_token = Column(Text, primary_key=True)
    card_id = Column(UUID(as_uuid=True), ForeignKey('cards.card_id'), nullable=False)
    status = Column(Text, nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    card = relationship('Card', back_populates='card_tokens')
    transactions = relationship('Tx', back_populates='card_token_rel')
    
    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive')", name='ck_card_tokens_status'),
    )


class Tx(Base):
    """Mock 카드사 기준 결제 승인/실패 이력"""
    __tablename__ = 'tx'
    
    tx_id = Column(Text, primary_key=True)
    card_token = Column(Text, ForeignKey('card_tokens.card_token'), nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(Text, nullable=False, default='KRW')
    approval_no = Column(Text, nullable=True)
    status = Column(Text, nullable=False)
    idempotency_key = Column(Text, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    card_token_rel = relationship('CardToken', back_populates='transactions')
    
    # Constraints
    __table_args__ = (
        CheckConstraint('amount > 0', name='ck_tx_amount'),
        CheckConstraint("status IN ('success', 'failed', 'cancelled')", name='ck_tx_status'),
    )
