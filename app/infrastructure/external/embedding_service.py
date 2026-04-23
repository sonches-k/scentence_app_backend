"""Сервис генерации embeddings через sentence-transformers."""

from typing import List
import logging

from app.core.interfaces import IEmbeddingService

logger = logging.getLogger(__name__)

# Модели, требующие query:/passage: префиксов (семейство E5)
_E5_MODELS = {
    "intfloat/multilingual-e5-large",
    "intfloat/multilingual-e5-base",
    "intfloat/multilingual-e5-small",
    "intfloat/e5-large-v2",
    "intfloat/e5-base-v2",
}


class SentenceTransformerEmbeddingService(IEmbeddingService):
    """Генерация embeddings локально через sentence-transformers.

    Поддерживает два семейства моделей:
      - cointegrated/rubert-tiny2 (312 dim) — без префиксов
      - intfloat/multilingual-e5-large (1024 dim) — требует prefix query:/passage:
    """

    def __init__(self, model_name: str = 'intfloat/multilingual-e5-large'):
        """
        Args:
            model_name: Название модели sentence-transformers.
        """
        from sentence_transformers import SentenceTransformer

        logger.info("Загрузка модели %s...", model_name)
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        self._use_e5_prefix = model_name in _E5_MODELS
        logger.info(
            "Модель загружена. Размерность: %d, E5-префиксы: %s",
            self.dimension,
            self._use_e5_prefix,
        )

    def generate_embedding(self, text: str) -> List[float]:
        """Генерирует embedding для поискового запроса пользователя.

        Для E5-моделей автоматически добавляет префикс 'query: '.

        Args:
            text: Текст запроса.

        Returns:
            Список float-значений размерности модели.
        """
        if self._use_e5_prefix:
            text = f"query: {text}"
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Генерация embeddings для батча текстов-документов (индексация).

        Для E5-моделей автоматически добавляет префикс 'passage: '.

        Args:
            texts: Список текстов ароматов.

        Returns:
            Список векторов.
        """
        if self._use_e5_prefix:
            texts = [f"passage: {t}" for t in texts]
        embeddings = self.model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
        return [emb.tolist() for emb in embeddings]
