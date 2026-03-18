"""Сервис генерации embeddings через sentence-transformers."""

from typing import List
import logging

from app.core.interfaces import IEmbeddingService

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddingService(IEmbeddingService):
    """Генерация embeddings локально через sentence-transformers."""

    def __init__(self, model_name: str = 'cointegrated/rubert-tiny2'):
        """
        Args:
            model_name: Название модели sentence-transformers
                       'cointegrated/rubert-tiny2' - 312 dim, русский
                       'paraphrase-multilingual-MiniLM-L12-v2' - 384 dim
        """
        from sentence_transformers import SentenceTransformer

        logger.info("Загрузка модели %s...", model_name)
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info("Модель загружена. Размерность: %d", self.dimension)

    def generate_embedding(self, text: str) -> List[float]:
        """
        Генерирует embedding вектор для текста.

        Args:
            text: Текст для векторизации

        Returns:
            List из 312 чисел (для rubert-tiny2)
        """
        embedding = self.model.encode(text)
        return embedding.tolist()

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Генерация embeddings для батча текстов (быстрее).

        Args:
            texts: Список текстов

        Returns:
            Список векторов
        """
        embeddings = self.model.encode(texts, show_progress_bar=True)
        return [emb.tolist() for emb in embeddings]
