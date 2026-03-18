"""
Интерфейсы репозиториев.

Определяют методы доступа к данным без привязки к конкретной реализации.
"""

from abc import ABC, abstractmethod
from typing import Optional

from datetime import datetime

from app.core.entities import (
    Perfume,
    Note,
    User,
    UserFavorite,
    SearchHistoryEntry,
    VerificationCode,
)


class IPerfumeRepository(ABC):
    """Интерфейс репозитория ароматов."""

    @abstractmethod
    def get_by_id(self, perfume_id: int) -> Optional[Perfume]:
        """Получить аромат по ID."""
        pass

    @abstractmethod
    def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[dict] = None,
    ) -> list[Perfume]:
        """Получить список ароматов с фильтрацией."""
        pass

    @abstractmethod
    def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 5,
        filters: Optional[dict] = None,
    ) -> list[tuple[Perfume, float]]:
        """Поиск по векторному сходству. Возвращает (аромат, score)."""
        pass

    @abstractmethod
    def find_similar(
        self,
        perfume_id: int,
        limit: int = 5,
    ) -> list[tuple[Perfume, float]]:
        """Найти похожие ароматы."""
        pass

    @abstractmethod
    def get_unique_brands(self) -> list[str]:
        """Получить список уникальных брендов."""
        pass

    @abstractmethod
    def get_unique_families(self) -> list[str]:
        """Получить список уникальных семейств."""
        pass

    @abstractmethod
    def get_unique_genders(self) -> list[str]:
        """Получить список уникальных значений пола."""
        pass

    @abstractmethod
    def get_unique_notes(self) -> list[str]:
        """Получить список уникальных нот."""
        pass

    @abstractmethod
    def get_unique_product_types(self) -> list[str]:
        """Получить список уникальных типов продукта."""
        pass


class IUserRepository(ABC):
    """Интерфейс репозитория пользователей."""

    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID."""
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        """Получить пользователя по email."""
        pass

    @abstractmethod
    def create(self, email: str, name: Optional[str] = None) -> User:
        """Создать пользователя."""
        pass

    @abstractmethod
    def get_favorites(self, user_id: int) -> list[Perfume]:
        """Получить избранные ароматы пользователя."""
        pass

    @abstractmethod
    def add_favorite(self, user_id: int, perfume_id: int) -> UserFavorite:
        """Добавить аромат в избранное."""
        pass

    @abstractmethod
    def remove_favorite(self, user_id: int, perfume_id: int) -> bool:
        """Удалить аромат из избранного."""
        pass

    @abstractmethod
    def is_favorite(self, user_id: int, perfume_id: int) -> bool:
        """Проверить, в избранном ли аромат."""
        pass

    @abstractmethod
    def get_search_history(
        self,
        user_id: int,
        limit: int = 100,
    ) -> list[SearchHistoryEntry]:
        """Получить историю поиска."""
        pass

    @abstractmethod
    def add_search_history(
        self,
        user_id: int,
        query_text: str,
        filters: Optional[dict] = None,
    ) -> SearchHistoryEntry:
        """Добавить запись в историю поиска."""
        pass

    @abstractmethod
    def update_name(self, user_id: int, name: str) -> User:
        """Обновить имя пользователя."""
        pass

    @abstractmethod
    def create_verification_code(
        self,
        email: str,
        code: str,
        expires_at: datetime,
    ) -> VerificationCode:
        """Создать код подтверждения."""
        pass

    @abstractmethod
    def get_latest_verification_code(self, email: str) -> Optional[VerificationCode]:
        """Получить последний активный код подтверждения для email."""
        pass

    @abstractmethod
    def increment_code_attempts(self, code_id: int) -> None:
        """Увеличить счётчик неверных попыток."""
        pass

    @abstractmethod
    def delete_verification_codes(self, email: str) -> None:
        """Удалить все коды подтверждения для email."""
        pass
