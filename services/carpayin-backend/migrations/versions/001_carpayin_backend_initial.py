"""Initial Car Pay-in DB schema

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
    
    # vehicles table
    op.create_table(
        'vehicles',
        sa.Column('car_id', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('car_sellname', sa.Text(), server_default='', nullable=False),
        sa.Column('plate', sa.String(20), server_default='', nullable=False),
        sa.Column('registered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('car_id')
    )
    op.create_index('idx_vehicles_user_id', 'vehicles', ['user_id'])
    op.create_index('idx_vehicles_plate', 'vehicles', ['plate'], unique=True, postgresql_where=sa.text("plate <> ''"))
    
    # vehicle_billing_keys table
    op.create_table(
        'vehicle_billing_keys',
        sa.Column('car_id', sa.Text(), nullable=False),
        sa.Column('billing_key', sa.Text(), nullable=False),
        sa.Column('card_last_four', sa.CHAR(4), nullable=False),
        sa.Column('status', sa.Text(), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'inactive')", name='ck_vehicle_billing_keys_status'),
        sa.CheckConstraint("card_last_four ~ '^[0-9]{4}$'", name='ck_vehicle_billing_keys_card_last_four'),
        sa.ForeignKeyConstraint(['car_id'], ['vehicles.car_id']),
        sa.PrimaryKeyConstraint('car_id'),
        sa.UniqueConstraint('billing_key')
    )
    
    # parking_sessions table
    op.create_table(
        'parking_sessions',
        sa.Column('session_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('pms_session_id', sa.Text(), nullable=True),
        sa.Column('car_id', sa.Text(), nullable=False),
        sa.Column('lot_id', sa.Text(), nullable=False),
        sa.Column('plate', sa.String(20), nullable=False),
        sa.Column('entry_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('exit_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Text(), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'completed', 'cancelled')", name='ck_parking_sessions_status'),
        sa.ForeignKeyConstraint(['car_id'], ['vehicles.car_id']),
        sa.PrimaryKeyConstraint('session_id')
    )
    op.create_index('idx_parking_sessions_car_id', 'parking_sessions', ['car_id'])
    op.create_index('idx_parking_sessions_status', 'parking_sessions', ['status'])
    op.create_index('idx_parking_sessions_pms_session_id', 'parking_sessions', ['pms_session_id'])
    op.create_index('uniq_active_session_per_car', 'parking_sessions', ['car_id'], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_index('uniq_parking_sessions_lot_pms', 'parking_sessions', ['lot_id', 'pms_session_id'], unique=True, postgresql_where=sa.text('pms_session_id IS NOT NULL'))
    
    # transactions table
    op.create_table(
        'transactions',
        sa.Column('tx_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('car_id', sa.Text(), nullable=False),
        sa.Column('billing_key', sa.Text(), nullable=False),
        sa.Column('pg_tx_id', sa.Text(), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.CHAR(3), server_default='KRW', nullable=False),
        sa.Column('status', sa.Text(), server_default='pending', nullable=False),
        sa.Column('approval_no', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.Text(), nullable=False),
        sa.Column('failed_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('amount > 0', name='ck_transactions_amount'),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name='ck_transactions_currency'),
        sa.CheckConstraint("status IN ('pending', 'success', 'failed', 'cancelled')", name='ck_transactions_status'),
        sa.ForeignKeyConstraint(['session_id'], ['parking_sessions.session_id']),
        sa.ForeignKeyConstraint(['car_id'], ['vehicles.car_id']),
        sa.PrimaryKeyConstraint('tx_id'),
        sa.UniqueConstraint('idempotency_key')
    )
    op.create_index('idx_transactions_session_id', 'transactions', ['session_id'])
    op.create_index('idx_transactions_car_id', 'transactions', ['car_id'])
    op.create_index('idx_transactions_billing_key', 'transactions', ['billing_key'])
    op.create_index('idx_transactions_pg_tx_id', 'transactions', ['pg_tx_id'])
    
    # app_refresh_tokens table
    op.create_table(
        'app_refresh_tokens',
        sa.Column('refresh_token_hash', sa.CHAR(64), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('car_id', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'revoked', 'expired')", name='ck_app_refresh_tokens_status'),
        sa.CheckConstraint("refresh_token_hash ~ '^[a-f0-9]{64}$'", name='ck_app_refresh_tokens_hash'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['car_id'], ['vehicles.car_id']),
        sa.PrimaryKeyConstraint('refresh_token_hash')
    )
    op.create_index('idx_app_refresh_tokens_user_id', 'app_refresh_tokens', ['user_id'])
    op.create_index('idx_app_refresh_tokens_car_id', 'app_refresh_tokens', ['car_id'])
    op.create_index('idx_app_refresh_tokens_expires_at', 'app_refresh_tokens', ['expires_at'])
    
    # hyundai_tokens table
    op.create_table(
        'hyundai_tokens',
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('hyundai_refresh_token_encrypted', sa.Text(), nullable=False),
        sa.Column('refresh_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('user_id')
    )


def downgrade():
    op.drop_table('hyundai_tokens')
    op.drop_table('app_refresh_tokens')
    op.drop_table('transactions')
    op.drop_table('parking_sessions')
    op.drop_table('vehicle_billing_keys')
    op.drop_table('vehicles')
    op.drop_table('users')
    op.execute('DROP EXTENSION IF EXISTS pgcrypto')
