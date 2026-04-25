"""
Use Cases - бизнес-логика приложения.

Каждый use case представляет один сценарий использования.
Зависят только от интерфейсов, не от конкретных реализаций.
"""

from app.core.use_cases.auth import (
    RegisterUseCase,
    LoginUseCase,
    VerifyCodeUseCase,
)
from app.core.use_cases.search import (
    SemanticSearchUseCase,
    FindSimilarUseCase,
)
from app.core.use_cases.perfume import (
    GetPerfumeUseCase,
    GetFiltersUseCase,
    SuggestBrandsUseCase,
    SuggestNotesUseCase,
)
from app.core.use_cases.user import (
    GetFavoritesUseCase,
    AddFavoriteUseCase,
    RemoveFavoriteUseCase,
    GetSearchHistoryUseCase,
    DeleteSearchHistoryEntryUseCase,
    ClearSearchHistoryUseCase,
)

__all__ = [
    "RegisterUseCase",
    "LoginUseCase",
    "VerifyCodeUseCase",
    "SemanticSearchUseCase",
    "FindSimilarUseCase",
    "GetPerfumeUseCase",
    "GetFiltersUseCase",
    "SuggestBrandsUseCase",
    "SuggestNotesUseCase",
    "GetFavoritesUseCase",
    "AddFavoriteUseCase",
    "RemoveFavoriteUseCase",
    "GetSearchHistoryUseCase",
    "DeleteSearchHistoryEntryUseCase",
    "ClearSearchHistoryUseCase",
]
