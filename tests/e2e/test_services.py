"""
E2E-тесты внешних сервисов: embedding, LLM, JWT, email.

Запуск: pytest tests/e2e/test_services.py -v
Требует: sentence-transformers, DEEPSEEK_API_KEY в .env.
"""

import pytest

from app.core.value_objects import NotePyramid

pytestmark = pytest.mark.e2e


class TestEmbeddingService:

    def test_generate_embedding(self, embedding_service):
        """Генерация эмбеддинга — вектор из 312 чисел."""
        embedding = embedding_service.generate_embedding("свежий цитрусовый аромат")

        assert isinstance(embedding, list)
        assert len(embedding) == 312
        assert all(isinstance(x, float) for x in embedding)

    def test_generate_embedding_different_texts(self, embedding_service):
        """Разные тексты дают разные эмбеддинги."""
        emb1 = embedding_service.generate_embedding("свежий лимонный аромат")
        emb2 = embedding_service.generate_embedding("тяжёлый восточный мускус")

        assert emb1 != emb2

    def test_generate_embedding_similar_texts(self, embedding_service):
        """Похожие тексты дают близкие эмбеддинги (cosine similarity > 0.5)."""
        emb1 = embedding_service.generate_embedding("свежий цитрусовый аромат на лето")
        emb2 = embedding_service.generate_embedding("лёгкий цитрусовый парфюм для лета")

        # Cosine similarity
        import math
        dot = sum(a * b for a, b in zip(emb1, emb2))
        norm1 = math.sqrt(sum(a * a for a in emb1))
        norm2 = math.sqrt(sum(b * b for b in emb2))
        similarity = dot / (norm1 * norm2)

        assert similarity > 0.5, f"Cosine similarity {similarity:.3f} слишком низкий"

    def test_generate_embeddings_batch(self, embedding_service):
        """Батч-генерация — по вектору на каждый текст."""
        texts = ["аромат 1", "аромат 2", "аромат 3"]
        embeddings = embedding_service.generate_embeddings_batch(texts)

        assert len(embeddings) == 3
        assert all(len(e) == 312 for e in embeddings)

    def test_embedding_dimension_matches_config(self, embedding_service):
        """Размерность совпадает с заявленной моделью."""
        assert embedding_service.dimension == 312


class TestDeepSeekLLMService:

    def test_generate_search_explanation(self, llm_service):
        """Генерация пояснения — непустая строка на русском."""
        perfumes = [
            {
                "name": "Chanel No. 5",
                "brand": "Chanel",
                "family": "Floral",
                "gender": "Female",
                "notes": ["Бергамот", "Роза", "Мускус"],
                "top_notes": ("Бергамот",),
                "middle_notes": ("Роза",),
                "base_notes": ("Мускус",),
                "tags": ["классический", "цветочный"],
            },
        ]
        explanation = llm_service.generate_search_explanation(
            query="нежный цветочный аромат",
            perfumes=perfumes,
        )

        assert isinstance(explanation, str)
        assert len(explanation) > 20

    def test_generate_search_explanation_empty_perfumes(self, llm_service):
        """Пустой список ароматов — возвращает fallback-строку."""
        explanation = llm_service.generate_search_explanation(
            query="любой аромат",
            perfumes=[],
        )

        assert isinstance(explanation, str)
        assert len(explanation) > 0

    def test_extract_note_pyramid(self, llm_service):
        """Извлечение пирамиды нот — возвращает NotePyramid с данными."""
        pyramid = llm_service.extract_note_pyramid("тёплый ванильный аромат с корицей")

        assert isinstance(pyramid, NotePyramid)
        # Хотя бы один уровень должен быть непустым
        total_notes = len(pyramid.top) + len(pyramid.middle) + len(pyramid.base)
        assert total_notes > 0, "Пирамида полностью пустая"

    def test_extract_note_pyramid_russian_notes(self, llm_service):
        """Пирамида содержит ноты на русском."""
        pyramid = llm_service.extract_note_pyramid("свежий морской аромат с солью и цитрусами")

        all_notes = list(pyramid.top) + list(pyramid.middle) + list(pyramid.base)
        # Хотя бы одна нота должна быть на русском (кириллица)
        has_russian = any(
            any("\u0400" <= ch <= "\u04ff" for ch in note)
            for note in all_notes
        )
        assert has_russian, f"Нет русских нот: {all_notes}"


class TestJWTService:

    def test_create_and_decode_token(self, jwt_service):
        """Создание и декодирование JWT — round-trip."""
        token = jwt_service.create_token(user_id=42)

        assert isinstance(token, str)
        assert len(token) > 20

        decoded_id = jwt_service.decode_token(token)
        assert decoded_id == 42

    def test_decode_invalid_token(self, jwt_service):
        """Невалидный токен — ValueError."""
        with pytest.raises(ValueError):
            jwt_service.decode_token("invalid.token.here")

    def test_decode_empty_token(self, jwt_service):
        """Пустой токен — ValueError."""
        with pytest.raises(ValueError):
            jwt_service.decode_token("")

    def test_different_users_different_tokens(self, jwt_service):
        """Разные user_id — разные токены."""
        token1 = jwt_service.create_token(user_id=1)
        token2 = jwt_service.create_token(user_id=2)

        assert token1 != token2


class TestEmailService:

    def test_send_console_does_not_raise(self, email_service):
        """Console backend — не бросает исключений."""
        # EMAIL_BACKEND=console по умолчанию
        email_service.send_verification_code("test@example.com", "123456")
        # Если дошли сюда — OK, код просто выведен в лог
