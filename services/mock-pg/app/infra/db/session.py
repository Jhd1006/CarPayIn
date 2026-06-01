import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _requires_explicit_env() -> bool:
    return os.getenv("APP_ENV", "local").strip().lower() in {
        "aws",
        "staging",
        "prod",
        "production",
    }


def _database_url() -> str:
    value = os.getenv("MOCK_PG_DATABASE_URL", "").strip()
    if value:
        return value
    if _requires_explicit_env():
        raise RuntimeError("MOCK_PG_DATABASE_URL environment variable is required")
    return "postgresql+psycopg://dev_user:dev_pass@localhost:5434/mock_pg_dev"


DATABASE_URL = _database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
