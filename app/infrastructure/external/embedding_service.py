from typing import List
import logging

from app.core.interfaces import IEmbeddingService

logger = logging.getLogger(__name__)

_E5_MODEL = "intfloat/multilingual-e5-large"


class SentenceTransformerEmbeddingService(IEmbeddingService):
    """Генерация embeddings локально через sentence-transformers.

    Использует модель intfloat/multilingual-e5-large (1024 dim),
    требующую префиксов 'query: ' для запросов и 'passage: ' для документов.
    """

    def __init__(self, model_name: str = _E5_MODEL):
        from sentence_transformers import SentenceTransformer

        logger.info("Загрузка модели %s...", model_name)
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info("Модель загружена. Размерность: %d", self.dimension)

    def generate_embedding(self, text: str) -> List[float]:
        text = f"query: {text}"
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        texts = [f"passage: {t}" for t in texts]
        embeddings = self.model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
        return [emb.tolist() for emb in embeddings]
