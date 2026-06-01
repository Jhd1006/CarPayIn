"""Add payment notification outbox

Revision ID: 002_payment_notification_outbox
Revises: 001_initial
Create Date: 2026-06-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '002_payment_notification_outbox'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'payment_notification_outbox',
        sa.Column(
            'notification_id',
            postgresql.UUID(as_uuid=True),
            server_default=sa.text('gen_random_uuid()'),
            nullable=False,
        ),
        sa.Column('tx_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('car_id', sa.Text(), nullable=False),
        sa.Column(
            'event_type',
            sa.Text(),
            server_default='payment.completed',
            nullable=False,
        ),
        sa.Column('channel', sa.Text(), server_default='iot', nullable=False),
        sa.Column('destination', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.Text(), server_default='pending', nullable=False),
        sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('max_attempts', sa.Integer(), server_default=sa.text('5'), nullable=False),
        sa.Column(
            'next_attempt_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_reason', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "event_type IN ('payment.completed')",
            name='ck_payment_notification_outbox_event_type',
        ),
        sa.CheckConstraint("channel IN ('iot')", name='ck_payment_notification_outbox_channel'),
        sa.CheckConstraint(
            "status IN ('pending', 'publishing', 'published', 'delivered', 'failed', 'dead')",
            name='ck_payment_notification_outbox_status',
        ),
        sa.CheckConstraint('attempts >= 0', name='ck_payment_notification_outbox_attempts'),
        sa.CheckConstraint('max_attempts > 0', name='ck_payment_notification_outbox_max_attempts'),
        sa.ForeignKeyConstraint(['car_id'], ['vehicles.car_id']),
        sa.ForeignKeyConstraint(['session_id'], ['parking_sessions.session_id']),
        sa.ForeignKeyConstraint(['tx_id'], ['transactions.tx_id']),
        sa.PrimaryKeyConstraint('notification_id'),
        sa.UniqueConstraint('tx_id', 'event_type', name='uniq_payment_notification_outbox_tx_event'),
    )
    op.create_index(
        'idx_payment_notification_outbox_status_next_attempt',
        'payment_notification_outbox',
        ['status', 'next_attempt_at'],
    )
    op.create_index(
        'idx_payment_notification_outbox_car_id',
        'payment_notification_outbox',
        ['car_id'],
    )
    op.create_index(
        'idx_payment_notification_outbox_session_id',
        'payment_notification_outbox',
        ['session_id'],
    )


def downgrade():
    op.drop_index(
        'idx_payment_notification_outbox_session_id',
        table_name='payment_notification_outbox',
    )
    op.drop_index(
        'idx_payment_notification_outbox_car_id',
        table_name='payment_notification_outbox',
    )
    op.drop_index(
        'idx_payment_notification_outbox_status_next_attempt',
        table_name='payment_notification_outbox',
    )
    op.drop_table('payment_notification_outbox')
