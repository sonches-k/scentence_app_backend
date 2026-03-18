"""
Интерфейсы внешних сервисов.

Определяют контракты для взаимодействия с внешними API.
Реализации живут в app/infrastructure/ — core их не импортирует.
"""

from abc import ABC, abstractmethod

from app.core.entities import NotePyramid


class IEmbeddingService(ABC):
    """Интерфейс сервиса генерации эмбеддингов."""

    @abstractmethod
    def generate_embedding(self, text: str) -> list[float]:
        """Сгенерировать эмбеддинг для текста."""
        pass

    @abstractmethod
    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Сгенерировать эмбеддинги для списка текстов."""
        pass


class ILLMService(ABC):
    """Интерфейс сервиса LLM для генерации текста."""

    @abstractmethod
    def generate_search_explanation(
        self,
        query: str,
        perfumes: list[dict],
    ) -> str:
        """Сгенерировать пояснение к результатам поиска."""
        pass

    @abstractmethod
    def extract_note_pyramid(self, query: str) -> NotePyramid:
        """Извлечь пирамиду нот из запроса пользователя."""
        pass


class IEmailService(ABC):
    """Интерфейс сервиса отправки email."""

    @abstractmethod
    def send_verification_code(self, email: str, code: str) -> None:
        """Отправить 6-значный код подтверждения на указанный email."""
        pass


class IJWTService(ABC):
    """Интерфейс сервиса JWT-токенов."""

    @abstractmethod
    def create_token(self, user_id: int) -> str:
        """Создать JWT access-токен для пользователя."""
        pass

    @abstractmethod
    def decode_token(self, token: str) -> int:
        """Декодировать токен и вернуть user_id. Raises ValueError если невалиден."""
        pass
