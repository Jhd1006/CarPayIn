"""Initial Mock Card DB schema

Revision ID: 001_initial
Revises: 
Create Date: 2025-05-26 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgcrypto extension for gen_random_uuid()
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')
    
    # users table
    op.create_table(
        'users',
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), server_default='', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('user_id')
    )
    
    # cards table
    op.create_table(
        'cards',
        sa.Column('card_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('encrypted_card_num', sa.Text(), nullable=False),
        sa.Column('cvc_hmac', sa.Text(), nullable=True),
        sa.Column('exp_month', sa.Integer(), nullable=False),
        sa.Column('exp_year', sa.Integer(), nullable=False),
        sa.Column('status', sa.Text(), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('exp_month BETWEEN 1 AND 12', name='ck_cards_exp_month'),
        sa.CheckConstraint("status IN ('active', 'inactive', 'expired')", name='ck_cards_status'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('card_id'),
        sa.UniqueConstraint('user_id', 'encrypted_card_num', name='uq_cards_user_encrypted_card_num')
    )
    
    # card_tokens table
    op.create_table(
        'card_tokens',
        sa.Column('card_token', sa.Text(), nullable=False),
        sa.Column('card_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Text(), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('active', 'inactive')", name='ck_card_tokens_status'),
        sa.ForeignKeyConstraint(['card_id'], ['cards.card_id']),
        sa.PrimaryKeyConstraint('card_token')
    )
    
    # tx table
    op.create_table(
        'tx',
        sa.Column('tx_id', sa.Text(), nullable=False),
        sa.Column('card_token', sa.Text(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.Text(), server_default='KRW', nullable=False),
        sa.Column('approval_no', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('idempotency_key', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('amount > 0', name='ck_tx_amount'),
        sa.CheckConstraint("status IN ('success', 'failed', 'cancelled')", name='ck_tx_status'),
        sa.ForeignKeyConstraint(['card_token'], ['card_tokens.card_token']),
        sa.PrimaryKeyConstraint('tx_id'),
        sa.UniqueConstraint('idempotency_key')
    )


def downgrade():
    op.drop_table('tx')
    op.drop_table('card_tokens')
    op.drop_table('cards')
    op.drop_table('users')
    op.execute('DROP EXTENSION IF EXISTS pgcrypto')
