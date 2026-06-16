"""Add paid status to parking_sessions

Revision ID: 004_add_paid_status
Revises: 003_drop_pre_registrations
Create Date: 2026-06-16 00:00:00
"""
from alembic import op

revision = '004_add_paid_status'
down_revision = '003_drop_pre_registrations'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE parking_sessions DROP CONSTRAINT ck_pms_parking_sessions_status")
    op.execute("ALTER TABLE parking_sessions ADD CONSTRAINT ck_pms_parking_sessions_status CHECK (status IN ('active', 'paid', 'exited', 'cancelled'))")


def downgrade():
    op.execute("ALTER TABLE parking_sessions DROP CONSTRAINT ck_pms_parking_sessions_status")
    op.execute("ALTER TABLE parking_sessions ADD CONSTRAINT ck_pms_parking_sessions_status CHECK (status IN ('active', 'exited', 'cancelled'))")
