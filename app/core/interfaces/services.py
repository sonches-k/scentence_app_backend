from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from app.core.entities import NotePyramid


class IEmbeddingService(ABC):

    @abstractmethod
    def generate_embedding(self, text: str) -> list[float]:
        pass

    @abstractmethod
    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        pass


class ILLMService(ABC):

    @abstractmethod
    def generate_search_explanation(self, query: str, perfumes: list[dict]) -> str:
        pass

    @abstractmethod
    def extract_note_pyramid(self, query: str) -> NotePyramid:
        pass


class IEmailService(ABC):

    @abstractmethod
    def send_verification_code(self, email: str, code: str) -> None:
        pass


class IJWTService(ABC):

    @abstractmethod
    def create_token(self, user_id: int) -> str:
        pass

    @abstractmethod
    def decode_token(self, token: str) -> int:
        """Raises ValueError если невалиден."""
        pass

    @abstractmethod
    def issue_refresh_credentials(self) -> tuple[str, datetime]:
        """Возвращает (token, expires_at UTC) для сохранения в БД."""
        pass


class ICacheService(ABC):

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int) -> None:
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass
