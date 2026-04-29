import pytest

from app.core.value_objects import NotePyramid

pytestmark = pytest.mark.e2e

_EXPECTED_DIM = 1024


class TestEmbeddingService:

    def test_generate_embedding(self, embedding_service):
        embedding = embedding_service.generate_embedding("свежий цитрусовый аромат")

        assert isinstance(embedding, list)
        assert len(embedding) == _EXPECTED_DIM
        assert all(isinstance(x, float) for x in embedding)

    def test_generate_embedding_different_texts(self, embedding_service):
        """Разные тексты → разные эмбеддинги."""
        emb1 = embedding_service.generate_embedding("свежий лимонный аромат")
        emb2 = embedding_service.generate_embedding("тяжёлый восточный мускус")

        assert emb1 != emb2

    def test_generate_embeddings_batch(self, embedding_service):
        texts = ["аромат 1", "аромат 2", "аромат 3"]
        embeddings = embedding_service.generate_embeddings_batch(texts)

        assert len(embeddings) == 3
        assert all(len(e) == _EXPECTED_DIM for e in embeddings)

    def test_embedding_is_normalized(self, embedding_service):
        """Вектор нормализован (норма ≈ 1.0)."""
        import math
        emb = embedding_service.generate_embedding("тест нормализации")
        norm = math.sqrt(sum(x * x for x in emb))
        assert abs(norm - 1.0) < 1e-4, f"Норма вектора: {norm:.6f}"


class TestDeepSeekLLMService:

    def test_generate_search_result(self, llm_service):
        """generate_search_result возвращает (str, NotePyramid)."""
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
            }
        ]
        explanation, pyramid = llm_service.generate_search_result(
            query="нежный цветочный аромат",
            perfumes=perfumes,
        )

        assert isinstance(explanation, str) and len(explanation) > 10
        assert isinstance(pyramid, NotePyramid)

    def test_generate_search_result_empty_perfumes(self, llm_service):
        """Пустой список ароматов → fallback без ошибки."""
        explanation, pyramid = llm_service.generate_search_result(
            query="любой аромат",
            perfumes=[],
        )

        assert isinstance(explanation, str) and len(explanation) > 0
        assert isinstance(pyramid, NotePyramid)


class TestJWTService:

    def test_create_and_decode_token(self, jwt_service):
        token = jwt_service.create_token(user_id=42)

        assert isinstance(token, str) and len(token) > 20
        assert jwt_service.decode_token(token) == 42

    def test_decode_invalid_token(self, jwt_service):
        with pytest.raises(ValueError):
            jwt_service.decode_token("invalid.token.here")

    def test_decode_empty_token(self, jwt_service):
        with pytest.raises(ValueError):
            jwt_service.decode_token("")

    def test_different_users_different_tokens(self, jwt_service):
        assert jwt_service.create_token(user_id=1) != jwt_service.create_token(user_id=2)

    def test_issue_refresh_credentials(self, jwt_service):
        from datetime import datetime, timezone

        secret, expires_at = jwt_service.issue_refresh_credentials()
        assert isinstance(secret, str) and len(secret) >= 32
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        assert expires_at > datetime.now(timezone.utc)


class TestEmailService:

    def test_send_console_does_not_raise(self, email_service):
        email_service.send_verification_code("test@example.com", "123456")
