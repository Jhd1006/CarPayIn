from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    mock_card_database_url: str = (
        "postgresql+psycopg://dev_user:dev_pass@localhost:5433/mock_card_dev"
    )

    # Security
    mock_card_security_secret: str = "mock-card-dev-secret"

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()