"""
Fixtures для e2e-тестов.

Требуют реальную PostgreSQL, DeepSeek API, sentence-transformers.
Запуск: pytest tests/e2e/ -v
"""

import pytest
from sqlalchemy.orm import Session

from app.infrastructure.config import settings
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.repositories import (
    SQLAlchemyPerfumeRepository,
    SQLAlchemyUserRepository,
)
from app.infrastructure.external.embedding_service import SentenceTransformerEmbeddingService
from app.infrastructure.external.deepseek_service import DeepSeekLLMService
from app.infrastructure.security.jwt_handler import JWTService
from app.infrastructure.services.email_service import EmailService


@pytest.fixture
def db_session():
    """Реальная сессия PostgreSQL с откатом после каждого теста."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def existing_perfume_id(db_session: Session) -> int:
    """ID существующего аромата в БД."""
    from sqlalchemy import text
    row = db_session.execute(text("SELECT id FROM perfumes LIMIT 1")).fetchone()
    if not row:
        pytest.skip("В БД нет ароматов")
    return row[0]


@pytest.fixture
def perfume_repo(db_session: Session) -> SQLAlchemyPerfumeRepository:
    """Реальный репозиторий ароматов."""
    return SQLAlchemyPerfumeRepository(db_session)


@pytest.fixture
def user_repo(db_session: Session) -> SQLAlchemyUserRepository:
    """Реальный репозиторий пользователей."""
    return SQLAlchemyUserRepository(db_session)


@pytest.fixture(scope="session")
def embedding_service() -> SentenceTransformerEmbeddingService:
    """
    Реальный embedding сервис (rubert-tiny2).
    scope=session — модель грузится один раз на всю сессию тестов.
    """
    return SentenceTransformerEmbeddingService("cointegrated/rubert-tiny2")


@pytest.fixture
def llm_service() -> DeepSeekLLMService:
    """Реальный DeepSeek LLM сервис."""
    if not settings.DEEPSEEK_API_KEY:
        pytest.skip("DEEPSEEK_API_KEY не задан")
    return DeepSeekLLMService()


@pytest.fixture
def jwt_service() -> JWTService:
    """Реальный JWT сервис."""
    return JWTService()


@pytest.fixture(autouse=True)
def _force_console_email():
    """Подмена EMAIL_BACKEND=console на время теста."""
    original = settings.EMAIL_BACKEND
    settings.EMAIL_BACKEND = "console"
    yield
    settings.EMAIL_BACKEND = original


@pytest.fixture
def email_service() -> EmailService:
    """Email сервис (console backend для тестов)."""
    return EmailService()
