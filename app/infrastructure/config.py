"""
Конфигурация приложения.

Загрузка переменных окружения и настроек.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import secrets


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения."""

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/perfume_db"

    # OpenAI API
    OPENAI_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_MODEL: str = "gpt-4-turbo-preview"

    # DeepSeek API
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # JWT
    JWT_SECRET: str = "change-this-jwt-secret-in-production"
    JWT_EXPIRE_DAYS: int = 7

    # Email
    EMAIL_BACKEND: str = "console"  # console | smtp
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USE_TLS: bool = True
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "noreply@perfume-app.ru"

    # Application
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Perfume Selection API"

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    # Embedding settings
    EMBEDDING_DIMENSION: int = 312  # rubert-tiny2
    EMBEDDING_BATCH_SIZE: int = 100

    # Search settings
    DEFAULT_SEARCH_LIMIT: int = 5
    MAX_SEARCH_QUERY_LENGTH: int = 1000
    MIN_SEARCH_QUERY_LENGTH: int = 3

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = True


# Singleton для настроек
settings = Settings()
