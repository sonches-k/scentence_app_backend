import os
import random

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.interfaces import IEmbeddingService
from app.infrastructure.config import settings
from app.infrastructure.database.models import Base
from app.infrastructure.database.repositories import (
    SQLAlchemyPerfumeRepository,
    SQLAlchemyUserRepository,
)
from app.infrastructure.security.jwt_handler import JWTService
from app.infrastructure.services.email_service import EmailService

_TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:password@localhost:5434/perfume_test",
)

_EMBEDDING_DIM = 1024


class FakeEmbeddingService(IEmbeddingService):
    """Deterministic fake embeddings — no model loading required."""

    dimension: int = _EMBEDDING_DIM

    def generate_embedding(self, text: str) -> list[float]:
        rng = random.Random(hash(text) & 0xFFFFFFFF)
        vec = [rng.gauss(0.0, 1.0) for _ in range(_EMBEDDING_DIM)]
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.generate_embedding(t) for t in texts]


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(_TEST_DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="session")
def seed_perfumes(test_engine) -> list[int]:
    """
    Insert 5 test perfumes with fake 1024-dim embeddings.
    Committed once for the whole session; cleaned up by drop_all in test_engine.
    """
    from app.infrastructure.database.models import (
        NoteModel,
        PerfumeEmbeddingModel,
        PerfumeModel,
        PerfumeNoteModel,
    )

    _PERFUMES = [
        {"name": "Rose Garden", "brand": "TestBrand", "gender": "Female",
         "family": "Floral", "product_type": "EDP", "category": "Люкс",
         "description": "Нежный цветочный аромат"},
        {"name": "Ocean Breeze", "brand": "TestBrand", "gender": "Male",
         "family": "Fresh", "product_type": "EDT", "category": "Масс-маркет",
         "description": "Свежий морской аромат"},
        {"name": "Oud Noir", "brand": "ArabBrand", "gender": "Unisex",
         "family": "Oriental", "product_type": "Parfum", "category": "Восточная",
         "description": "Глубокий восточный аромат"},
        {"name": "Vanilla Dream", "brand": "TestBrand", "gender": "Female",
         "family": "Gourmand", "product_type": "EDP", "category": "Селективная",
         "description": "Сладкий ванильный аромат"},
        {"name": "Forest Walk", "brand": "NicheBrand", "gender": "Male",
         "family": "Woody", "product_type": "EDP", "category": "Нишевая",
         "description": "Древесный аромат с мхом"},
    ]

    fake = FakeEmbeddingService()

    with Session(test_engine) as session:
        note_citrus = NoteModel(name="Бергамот-тест", category="Citrus")
        note_floral = NoteModel(name="Роза-тест", category="Floral")
        session.add_all([note_citrus, note_floral])
        session.flush()

        ids = []
        for data in _PERFUMES:
            perfume = PerfumeModel(**data)
            session.add(perfume)
            session.flush()
            session.add(PerfumeNoteModel(perfume_id=perfume.id, note_id=note_citrus.id, level="Top"))
            session.add(PerfumeNoteModel(perfume_id=perfume.id, note_id=note_floral.id, level="Middle"))
            emb = fake.generate_embedding(f"{data['name']} {data['description']}")
            session.add(PerfumeEmbeddingModel(perfume_id=perfume.id, embedding=emb))
            ids.append(perfume.id)

        session.commit()

    return ids


@pytest.fixture
def db_session(test_engine, seed_perfumes):
    """
    Fresh session per test. Uncommitted changes are rolled back on teardown.
    Committed changes (e.g. users created by auth tests) persist within the
    session but are wiped when the test DB is dropped at the end of the run.
    """
    with Session(test_engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def existing_perfume_id(seed_perfumes) -> int:
    return seed_perfumes[0]


@pytest.fixture
def perfume_repo(db_session) -> SQLAlchemyPerfumeRepository:
    return SQLAlchemyPerfumeRepository(db_session)


@pytest.fixture
def user_repo(db_session) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(db_session)


@pytest.fixture(scope="session")
def embedding_service() -> FakeEmbeddingService:
    return FakeEmbeddingService()


@pytest.fixture
def llm_service():
    if not settings.DEEPSEEK_API_KEY:
        pytest.skip("DEEPSEEK_API_KEY не задан")
    from app.infrastructure.external.deepseek_service import DeepSeekLLMService
    return DeepSeekLLMService()


@pytest.fixture
def jwt_service() -> JWTService:
    return JWTService()


@pytest.fixture(autouse=True)
def _force_console_email():
    original = settings.EMAIL_BACKEND
    settings.EMAIL_BACKEND = "console"
    yield
    settings.EMAIL_BACKEND = original


@pytest.fixture
def email_service() -> EmailService:
    return EmailService()
