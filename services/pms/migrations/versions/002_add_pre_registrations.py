"""Add PMS pre-registered plates.

Revision ID: 002_add_pre_registrations
Revises: 001_initial
Create Date: 2026-05-27 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "002_add_pre_registrations"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pre_registrations",
        sa.Column("lot_id", sa.Text(), nullable=False),
        sa.Column("plate", sa.String(20), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            server_default="pre_registered",
            nullable=False,
        ),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pre_registered', 'consumed', 'cancelled')",
            name="ck_pms_pre_registrations_status",
        ),
        sa.PrimaryKeyConstraint("lot_id", "plate"),
    )
    op.create_index(
        "idx_pms_pre_registrations_status",
        "pre_registrations",
        ["status"],
    )


def downgrade():
    op.drop_index("idx_pms_pre_registrations_status", table_name="pre_registrations")
    op.drop_table("pre_registrations")
