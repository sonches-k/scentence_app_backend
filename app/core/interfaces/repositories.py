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
    StoredRefreshToken,
)


class IPerfumeRepository(ABC):

    @abstractmethod
    def get_by_id(self, perfume_id: int) -> Optional[Perfume]:
        pass

    @abstractmethod
    def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[dict] = None,
    ) -> list[Perfume]:
        pass

    @abstractmethod
    def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 5,
        filters: Optional[dict] = None,
    ) -> list[tuple[Perfume, float]]:
        """Возвращает [(аромат, cosine_score)]."""
        pass

    @abstractmethod
    def find_similar(self, perfume_id: int, limit: int = 5) -> list[tuple[Perfume, float]]:
        pass

    @abstractmethod
    def get_unique_brands(self) -> list[str]:
        pass

    @abstractmethod
    def get_unique_families(self) -> list[str]:
        pass

    @abstractmethod
    def get_unique_genders(self) -> list[str]:
        pass

    @abstractmethod
    def get_unique_notes(self) -> list[str]:
        pass

    @abstractmethod
    def get_unique_product_types(self) -> list[str]:
        pass


class IUserRepository(ABC):

    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional[User]:
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    def create(self, email: str, name: Optional[str] = None) -> User:
        pass

    @abstractmethod
    def get_favorites(self, user_id: int) -> list[Perfume]:
        pass

    @abstractmethod
    def add_favorite(self, user_id: int, perfume_id: int) -> UserFavorite:
        pass

    @abstractmethod
    def remove_favorite(self, user_id: int, perfume_id: int) -> bool:
        pass

    @abstractmethod
    def is_favorite(self, user_id: int, perfume_id: int) -> bool:
        pass

    @abstractmethod
    def get_search_history(self, user_id: int, limit: int = 100) -> list[SearchHistoryEntry]:
        pass

    @abstractmethod
    def add_search_history(
        self,
        user_id: int,
        query_text: str,
        filters: Optional[dict] = None,
    ) -> SearchHistoryEntry:
        pass

    @abstractmethod
    def update_name(self, user_id: int, name: str) -> User:
        pass

    @abstractmethod
    def create_verification_code(self, email: str, code: str, expires_at: datetime) -> VerificationCode:
        pass

    @abstractmethod
    def get_latest_verification_code(self, email: str) -> Optional[VerificationCode]:
        pass

    @abstractmethod
    def increment_code_attempts(self, code_id: int) -> None:
        pass

    @abstractmethod
    def delete_verification_codes(self, email: str) -> None:
        pass

    @abstractmethod
    def create_refresh_token(self, user_id: int, token: str, expires_at: datetime) -> None:
        pass

    @abstractmethod
    def get_refresh_token(self, token: str) -> Optional[StoredRefreshToken]:
        pass

    @abstractmethod
    def delete_refresh_token(self, token: str) -> None:
        pass

    @abstractmethod
    def delete_user_refresh_tokens(self, user_id: int) -> None:
        pass
