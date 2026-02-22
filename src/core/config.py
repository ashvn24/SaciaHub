"""
Centralized configuration management using Pydantic BaseSettings.
All config is environment-driven with dev/staging/prod support.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    PROJECT_TITLE: str = "SaciaHub API"
    PROJECT_VERSION: str = "1.0.0"
    APP_PORT: int = 8000
    HOST: str = "0.0.0.0"
    ENVIRONMENT: str = Field(default="development", description="development | staging | production")
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Database
    UID: str = ""
    DB_PASSWORD: str = ""
    DB: str = ""
    PSQL_SERVER: str = ""
    POOL_SIZE: int = 10
    MAX_OVERFLOW: int = 20
    POOL_TIMEOUT: int = 30
    POOL_RECYCLE: int = 1800

    # JWT / Auth
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 2
    ENCRYPTION_KEY: str = ""

    # Email
    SENDGRID_API_KEY: str = ""
    EMAIL: str = ""

    # S3 / Storage
    S3_REGION: str = ""
    S3_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_PRIVATE_KEY: str = ""

    # Sentry
    SENTRY_DSN: str = ""

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.UID}:{self.DB_PASSWORD}@{self.PSQL_SERVER}/{self.DB}"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
