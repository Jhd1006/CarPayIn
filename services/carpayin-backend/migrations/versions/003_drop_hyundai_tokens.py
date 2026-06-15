"""Drop hyundai_tokens table

hyundai refresh/access token은 OAuth callback 시 동기 사용 후 즉시 버리는 것으로 설계 변경.
초기 로그인 이후 현대 토큰이 필요한 흐름이 없으므로 저장 자체를 제거한다.

Revision ID: 003_drop_hyundai_tokens
Revises: 002_payment_notification_outbox
Create Date: 2026-06-10 00:00:00
"""
from alembic import op

revision = '003_drop_hyundai_tokens'
down_revision = '002_payment_notification_outbox'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('hyundai_tokens')


def downgrade():
    op.execute("""
        CREATE TABLE hyundai_tokens (
            user_id TEXT PRIMARY KEY,
            hyundai_refresh_token_encrypted TEXT NOT NULL,
            refresh_expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
