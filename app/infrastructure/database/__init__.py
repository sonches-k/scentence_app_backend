"""
Database infrastructure - подключение и работа с БД.
"""

from app.infrastructure.database.connection import (
    engine,
    SessionLocal,
    Base,
    get_db,
)
from app.infrastructure.database.models import (
    PerfumeModel,
    NoteModel,
    PerfumeNoteModel,
    PerfumeEmbeddingModel,
    PerfumeTagModel,
    UserModel,
    UserFavoriteModel,
    SearchHistoryModel,
    VerificationCodeModel,
)
from app.infrastructure.database.repositories import (
    SQLAlchemyPerfumeRepository,
    SQLAlchemyUserRepository,
)

__all__ = [
    "engine",
    "SessionLocal",
    "Base",
    "get_db",
    "PerfumeModel",
    "NoteModel",
    "PerfumeNoteModel",
    "PerfumeEmbeddingModel",
    "PerfumeTagModel",
    "UserModel",
    "UserFavoriteModel",
    "SearchHistoryModel",
    "VerificationCodeModel",
    "SQLAlchemyPerfumeRepository",
    "SQLAlchemyUserRepository",
]
