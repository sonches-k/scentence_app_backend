"""
Доменные сущности для пользователей.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any


@dataclass
class User:
    """Пользователь системы."""
    id: int
    email: str
    name: Optional[str] = None
    created_at: Optional[datetime] = None

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email!r})"


@dataclass
class UserFavorite:
    """Избранный аромат пользователя."""
    id: int
    user_id: int
    perfume_id: int
    added_at: Optional[datetime] = None

    def __repr__(self) -> str:
        return f"UserFavorite(id={self.id}, user_id={self.user_id}, perfume_id={self.perfume_id})"


@dataclass
class SearchHistoryEntry:
    """Запись в истории поиска."""
    id: int
    user_id: int
    query_text: str
    filters: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None

    def __repr__(self) -> str:
        return f"SearchHistoryEntry(id={self.id}, query={self.query_text!r})"


@dataclass
class VerificationCode:
    """Код подтверждения email."""
    id: int
    email: str
    code: str
    expires_at: datetime
    attempts: int
    created_at: Optional[datetime] = None
