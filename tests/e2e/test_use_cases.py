"""
E2E-тесты use cases с реальными зависимостями.

Запуск: pytest tests/e2e/test_use_cases.py -v
Требует: PostgreSQL с данными, DeepSeek API, sentence-transformers.
"""

import pytest

from app.core.entities import Perfume, PerfumeWithRelevance
from app.core.exceptions import PerfumeNotFoundError, UserNotFoundError
from app.core.use_cases.search import SemanticSearchUseCase, FindSimilarUseCase, SearchResult
from app.core.use_cases.perfume import GetPerfumeUseCase, GetFiltersUseCase, GetBrandsUseCase
from app.core.use_cases.user import (
    GetFavoritesUseCase,
    AddFavoriteUseCase,
    RemoveFavoriteUseCase,
    GetSearchHistoryUseCase,
)
from app.core.use_cases.auth import RegisterUseCase, VerifyCodeUseCase
from app.core.value_objects import NotePyramid


pytestmark = pytest.mark.e2e


class TestSemanticSearchE2E:

    def test_full_search_pipeline(self, perfume_repo, embedding_service, llm_service):
        """
        Полный пайплайн: текст → embedding → pgvector → LLM пояснение.
        Это ключевой тест: проверяет что весь RAG-пайплайн работает.
        """
        use_case = SemanticSearchUseCase(
            perfume_repository=perfume_repo,
            embedding_service=embedding_service,
            llm_service=llm_service,
        )

        result = use_case.execute(query="свежий цитрусовый аромат на лето", limit=3)

        assert isinstance(result, SearchResult)
        assert result.query == "свежий цитрусовый аромат на лето"
        assert result.total_found <= 3
        assert isinstance(result.explanation, str)
        assert len(result.explanation) > 10
        assert isinstance(result.note_pyramid, NotePyramid)

        for p in result.perfumes:
            assert isinstance(p, PerfumeWithRelevance)
            assert p.perfume.name
            assert 0.0 <= p.relevance <= 1.0

    def test_search_with_filters(self, perfume_repo, embedding_service, llm_service):
        """Поиск с фильтрами — все результаты соответствуют фильтру."""
        from app.core.value_objects import SearchFilters

        use_case = SemanticSearchUseCase(
            perfume_repository=perfume_repo,
            embedding_service=embedding_service,
            llm_service=llm_service,
        )
        filters = SearchFilters.from_lists(genders=["Female"])
        result = use_case.execute(
            query="нежный цветочный аромат",
            filters=filters,
            limit=5,
        )

        for p in result.perfumes:
            assert p.perfume.gender == "Female"

    def test_search_returns_notes_and_tags(self, perfume_repo, embedding_service, llm_service):
        """Результаты содержат ноты и теги (RAG-контекст)."""
        use_case = SemanticSearchUseCase(
            perfume_repository=perfume_repo,
            embedding_service=embedding_service,
            llm_service=llm_service,
        )
        result = use_case.execute(query="древесный мускусный аромат", limit=3)

        # Хотя бы у одного аромата должны быть ноты
        has_notes = any(len(p.perfume.notes) > 0 for p in result.perfumes)
        assert has_notes, "Ни у одного аромата нет нот"


class TestFindSimilarE2E:

    def test_find_similar(self, perfume_repo, existing_perfume_id):
        """Поиск похожих — возвращает ароматы, отличные от исходного."""
        use_case = FindSimilarUseCase(perfume_repository=perfume_repo)

        results = use_case.execute(perfume_id=existing_perfume_id, limit=3)

        assert len(results) <= 3
        for p in results:
            assert p.perfume.id != existing_perfume_id
            assert 0.0 <= p.relevance <= 1.0

    def test_find_similar_nonexistent(self, perfume_repo):
        """Несуществующий аромат — пустой список (нет эмбеддинга)."""
        use_case = FindSimilarUseCase(perfume_repository=perfume_repo)

        results = use_case.execute(perfume_id=999999, limit=3)

        assert results == []


class TestGetPerfumeE2E:

    def test_get_existing_perfume(self, perfume_repo, existing_perfume_id):
        """Получение существующего аромата с полными данными."""
        use_case = GetPerfumeUseCase(perfume_repository=perfume_repo)

        perfume = use_case.execute(perfume_id=existing_perfume_id)

        assert isinstance(perfume, Perfume)
        assert perfume.id == existing_perfume_id
        assert perfume.name
        assert perfume.brand

    def test_get_nonexistent_perfume(self, perfume_repo):
        """Несуществующий аромат — PerfumeNotFoundError."""
        use_case = GetPerfumeUseCase(perfume_repository=perfume_repo)

        with pytest.raises(PerfumeNotFoundError):
            use_case.execute(perfume_id=999999)


class TestGetFiltersE2E:

    def test_get_filters(self, perfume_repo):
        """Фильтры — все категории непустые."""
        use_case = GetFiltersUseCase(perfume_repository=perfume_repo)

        filters = use_case.execute()

        assert len(filters.genders) > 0
        assert len(filters.families) > 0
        assert len(filters.brands) > 0
        assert len(filters.notes) > 0
        assert len(filters.product_types) > 0


class TestGetBrandsE2E:

    def test_get_brands(self, perfume_repo):
        """Бренды — непустой отсортированный список."""
        use_case = GetBrandsUseCase(perfume_repository=perfume_repo)

        brands = use_case.execute()

        assert len(brands) > 0
        assert brands == sorted(brands)


class TestAuthWorkflowE2E:

    def test_register_sends_code(self, user_repo, email_service):
        """Регистрация — создаёт verification code в БД."""
        import uuid
        email = f"reg_{uuid.uuid4().hex[:8]}@example.com"
        use_case = RegisterUseCase(user_repo=user_repo, email_service=email_service)

        use_case.execute(email)

        code = user_repo.get_latest_verification_code(email)
        assert code is not None
        assert len(code.code) == 6
        assert code.attempts == 0

    def test_verify_creates_user_and_returns_jwt(self, user_repo, jwt_service, email_service):
        """Полный цикл: register → verify → JWT → decode → user_id."""
        import uuid
        email = f"verify_{uuid.uuid4().hex[:8]}@example.com"

        reg = RegisterUseCase(user_repo=user_repo, email_service=email_service)
        reg.execute(email)

        stored_code = user_repo.get_latest_verification_code(email)
        assert stored_code is not None

        verify = VerifyCodeUseCase(user_repo=user_repo, jwt_service=jwt_service)
        token = verify.execute(email, stored_code.code)

        assert isinstance(token, str)
        assert len(token) > 20

        user_id = jwt_service.decode_token(token)
        user = user_repo.get_by_id(user_id)
        assert user is not None
        assert user.email == email


class TestUserFavoritesE2E:

    def test_full_favorites_workflow(self, user_repo, perfume_repo, db_session, existing_perfume_id):
        """Добавить → получить → удалить избранное через use cases."""
        import uuid
        email = f"favuc_{uuid.uuid4().hex[:8]}@example.com"
        user = user_repo.create(email=email)
        pid = existing_perfume_id

        add_uc = AddFavoriteUseCase(
            user_repository=user_repo,
            perfume_repository=perfume_repo,
        )
        get_uc = GetFavoritesUseCase(user_repository=user_repo)
        rm_uc = RemoveFavoriteUseCase(user_repository=user_repo)

        fav = add_uc.execute(user.id, pid)
        assert fav.perfume_id == pid

        favorites = get_uc.execute(user.id)
        assert any(p.id == pid for p in favorites)

        removed = rm_uc.execute(user.id, pid)
        assert removed is True

        favorites = get_uc.execute(user.id)
        assert not any(p.id == pid for p in favorites)
