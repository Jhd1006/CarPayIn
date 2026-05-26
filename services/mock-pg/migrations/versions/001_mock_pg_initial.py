"""Initial Mock PG DB schema

Revision ID: 001_initial
Revises: 
Create Date: 2025-05-26 00:00:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgcrypto extension for gen_random_uuid()
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')
    
    # billing_keys table
    op.create_table(
        'billing_keys',
        sa.Column('billing_key', sa.Text(), nullable=False),
        sa.Column('order_id', sa.Text(), nullable=False),
        sa.Column('card_token', sa.Text(), nullable=False),
        sa.Column('card_last_four', sa.CHAR(4), server_default='', nullable=True),
        sa.Column('status', sa.Text(), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('active', 'inactive')", name='ck_billing_keys_status'),
        sa.PrimaryKeyConstraint('billing_key'),
        sa.UniqueConstraint('order_id')
    )
    
    # transactions table
    op.create_table(
        'transactions',
        sa.Column('pg_tx_id', sa.Text(), nullable=False),
        sa.Column('billing_key', sa.Text(), nullable=False),
        sa.Column('card_token', sa.Text(), nullable=False),
        sa.Column('card_tx_id', sa.Text(), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.Text(), server_default='KRW', nullable=False),
        sa.Column('approval_no', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), server_default='pending', nullable=False),
        sa.Column('idempotency_key', sa.Text(), nullable=False),
        sa.Column('failed_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('amount > 0', name='ck_pg_transactions_amount'),
        sa.CheckConstraint("status IN ('pending', 'success', 'failed', 'cancelled')", name='ck_pg_transactions_status'),
        sa.ForeignKeyConstraint(['billing_key'], ['billing_keys.billing_key']),
        sa.PrimaryKeyConstraint('pg_tx_id'),
        sa.UniqueConstraint('idempotency_key')
    )


def downgrade():
    op.drop_table('transactions')
    op.drop_table('billing_keys')
    op.execute('DROP EXTENSION IF EXISTS pgcrypto')
