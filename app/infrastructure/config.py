from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):

    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/perfume_db"
    REDIS_URL: Optional[str] = None

    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_SECRET: str
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    EMAIL_BACKEND: str = "console"  # console | smtp
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USE_TLS: bool = True
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "noreply@perfume-app.ru"

    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Perfume Selection API"

    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    DEFAULT_SEARCH_LIMIT: int = 5
    MAX_SEARCH_QUERY_LENGTH: int = 1000
    MIN_SEARCH_QUERY_LENGTH: int = 3

    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_BATCH_SIZE: int = 100

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
