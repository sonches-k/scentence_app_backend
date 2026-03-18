"""
Domain Entities - доменные сущности.

Чистые Python классы без внешних зависимостей.
Представляют бизнес-объекты приложения.
"""

from app.core.entities.perfume import (
    Perfume,
    Note,
    PerfumeNote,
    PerfumeWithRelevance,
)
from app.core.entities.user import User, UserFavorite, SearchHistoryEntry, VerificationCode
from app.core.value_objects import NotePyramid, PerfumeTag

__all__ = [
    "Perfume",
    "Note",
    "PerfumeNote",
    "NotePyramid",
    "PerfumeTag",
    "PerfumeWithRelevance",
    "User",
    "UserFavorite",
    "SearchHistoryEntry",
    "VerificationCode",
]
