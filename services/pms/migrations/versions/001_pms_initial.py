"""Initial PMS DB schema

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
    
    # parking_sessions table
    op.create_table(
        'parking_sessions',
        sa.Column('pms_session_id', sa.Text(), nullable=False),
        sa.Column('lot_id', sa.Text(), server_default='mock_lot_001', nullable=False),
        sa.Column('plate', sa.String(20), server_default='', nullable=False),
        sa.Column('entry_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('exit_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Text(), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'paid', 'exited', 'cancelled')", name='ck_pms_parking_sessions_status'),
        sa.PrimaryKeyConstraint('pms_session_id')
    )
    op.create_index('idx_pms_parking_sessions_plate', 'parking_sessions', ['plate'])
    op.create_index('idx_pms_parking_sessions_status', 'parking_sessions', ['status'])
    op.create_index('uniq_active_pms_session_per_plate', 'parking_sessions', ['plate'], unique=True, postgresql_where=sa.text("status = 'active'"))
    
    # payment_requests table
    op.create_table(
        'payment_requests',
        sa.Column('payment_request_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('pms_session_id', sa.Text(), nullable=False),
        sa.Column('carpay_parking_session_id', sa.Text(), nullable=True),
        sa.Column('carpay_tx_id', sa.Text(), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.Text(), server_default='KRW', nullable=False),
        sa.Column('status', sa.Text(), server_default='pending', nullable=False),
        sa.Column('idempotency_key', sa.Text(), nullable=False),
        sa.Column('approval_no', sa.Text(), nullable=True),
        sa.Column('failed_reason', sa.Text(), nullable=True),
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('amount >= 0', name='ck_payment_requests_amount'),
        sa.CheckConstraint("status IN ('pending', 'success', 'failed', 'cancelled')", name='ck_payment_requests_status'),
        sa.ForeignKeyConstraint(['pms_session_id'], ['parking_sessions.pms_session_id']),
        sa.PrimaryKeyConstraint('payment_request_id'),
        sa.UniqueConstraint('idempotency_key')
    )
    op.create_index('idx_payment_requests_pms_session_id', 'payment_requests', ['pms_session_id'])
    op.create_index('idx_payment_requests_status', 'payment_requests', ['status'])
    op.create_index('idx_payment_requests_carpay_parking_session_id', 'payment_requests', ['carpay_parking_session_id'])
    op.create_index('idx_payment_requests_carpay_tx_id', 'payment_requests', ['carpay_tx_id'])


def downgrade():
    op.drop_table('payment_requests')
    op.drop_table('parking_sessions')
    op.execute('DROP EXTENSION IF EXISTS pgcrypto')
