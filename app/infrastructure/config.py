from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/perfume_db"

    # Redis
    REDIS_URL: Optional[str] = None

    # DeepSeek API
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # Security
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # JWT
    JWT_SECRET: str = "change-this-jwt-secret-in-production"
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

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

    # Search settings
    DEFAULT_SEARCH_LIMIT: int = 5
    MAX_SEARCH_QUERY_LENGTH: int = 1000
    MIN_SEARCH_QUERY_LENGTH: int = 3

    # Embedding settings (используются скриптами)
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_BATCH_SIZE: int = 100

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
