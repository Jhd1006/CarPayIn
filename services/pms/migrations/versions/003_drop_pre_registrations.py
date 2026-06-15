"""Drop pre_registrations table - moved to Redis with TTL

사전등록은 임시 상태이므로 DB 대신 Redis TTL 기반으로 관리한다.
key: pre_reg:{lot_id}:{plate}, TTL 1시간

Revision ID: 003_drop_pre_registrations
Revises: 002_add_pre_registrations
Create Date: 2026-06-10 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "003_drop_pre_registrations"
down_revision = "002_add_pre_registrations"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("idx_pms_pre_registrations_status", table_name="pre_registrations")
    op.drop_table("pre_registrations")


def downgrade():
    op.create_table(
        "pre_registrations",
        sa.Column("lot_id", sa.Text(), nullable=False),
        sa.Column("plate", sa.String(20), nullable=False),
        sa.Column("status", sa.Text(), server_default="pre_registered", nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pre_registered', 'consumed', 'cancelled')", name="ck_pms_pre_registrations_status"),
        sa.PrimaryKeyConstraint("lot_id", "plate"),
    )
    op.create_index("idx_pms_pre_registrations_status", "pre_registrations", ["status"])
