"""
Unit-тесты для SemanticSearchUseCase и FindSimilarUseCase.
"""

import pytest
from unittest.mock import MagicMock

from app.core.entities.perfume import PerfumeWithRelevance
from app.core.exceptions import PerfumeNotFoundError
from app.core.interfaces import ICacheService
from app.core.use_cases.search import SemanticSearchUseCase, FindSimilarUseCase, SearchResult
from app.core.value_objects import SearchFilters


pytestmark = pytest.mark.unit


class TestSemanticSearchUseCase:

    def _make_use_case(self, perfume_repo, embedding_service, llm_service, cache=None):
        return SemanticSearchUseCase(
            perfume_repository=perfume_repo,
            embedding_service=embedding_service,
            llm_service=llm_service,
            cache=cache,
        )

    def test_semantic_search_returns_results(
        self,
        mock_perfume_repository,
        mock_embedding_service,
        mock_llm_service,
        sample_perfumes,
    ):
        """Нормальный запрос — возвращает список результатов."""
        mock_perfume_repository.search_by_embedding.return_value = [
            (p, 0.9 - i * 0.05) for i, p in enumerate(sample_perfumes)
        ]
        use_case = self._make_use_case(
            mock_perfume_repository, mock_embedding_service, mock_llm_service
        )

        result = use_case.execute(query="тёплый восточный аромат", limit=5)

        assert isinstance(result, SearchResult)
        assert result.query == "тёплый восточный аромат"
        assert result.total_found == 5
        assert len(result.perfumes) == 5
        assert all(isinstance(p, PerfumeWithRelevance) for p in result.perfumes)
        mock_embedding_service.generate_embedding.assert_called_once_with("тёплый восточный аромат")
        mock_llm_service.generate_search_result.assert_called_once()

    def test_semantic_search_with_filters(
        self,
        mock_perfume_repository,
        mock_embedding_service,
        mock_llm_service,
        sample_perfumes,
    ):
        """Запрос с фильтрами — фильтры передаются в репозиторий."""
        mock_perfume_repository.search_by_embedding.return_value = [
            (sample_perfumes[0], 0.95)
        ]
        use_case = self._make_use_case(
            mock_perfume_repository, mock_embedding_service, mock_llm_service
        )
        filters = SearchFilters.from_lists(
            genders=["Female"],
            families=["Floral"],
        )

        result = use_case.execute(query="цветочный аромат", filters=filters, limit=5)

        call_kwargs = mock_perfume_repository.search_by_embedding.call_args
        passed_filters = call_kwargs.kwargs.get("filters") or call_kwargs.args[2]
        assert passed_filters is not None
        assert "genders" in passed_filters
        assert "Female" in passed_filters["genders"]
        assert result.filters_applied is not None

    def test_semantic_search_no_results(
        self,
        mock_perfume_repository,
        mock_embedding_service,
        mock_llm_service,
    ):
        """Нет совпадений — возвращает пустой список."""
        mock_perfume_repository.search_by_embedding.return_value = []
        use_case = self._make_use_case(
            mock_perfume_repository, mock_embedding_service, mock_llm_service
        )

        result = use_case.execute(query="несуществующий аромат", limit=5)

        assert result.total_found == 0
        assert result.perfumes == []

    def test_semantic_search_embedding_called_with_query(
        self,
        mock_perfume_repository,
        mock_embedding_service,
        mock_llm_service,
    ):
        """Эмбеддинг генерируется именно для переданного запроса."""
        mock_perfume_repository.search_by_embedding.return_value = []
        use_case = self._make_use_case(
            mock_perfume_repository, mock_embedding_service, mock_llm_service
        )
        query = "запрос для проверки"

        use_case.execute(query=query, limit=3)

        mock_embedding_service.generate_embedding.assert_called_once_with(query)

    def test_semantic_search_limit_passed_to_repo(
        self,
        mock_perfume_repository,
        mock_embedding_service,
        mock_llm_service,
    ):
        """Параметр limit передаётся в репозиторий."""
        mock_perfume_repository.search_by_embedding.return_value = []
        use_case = self._make_use_case(
            mock_perfume_repository, mock_embedding_service, mock_llm_service
        )

        use_case.execute(query="тест", limit=10)

        call_kwargs = mock_perfume_repository.search_by_embedding.call_args
        passed_limit = call_kwargs.kwargs.get("limit") or call_kwargs.args[1]
        assert passed_limit == 10

    def test_semantic_search_note_pyramid_in_result(
        self,
        mock_perfume_repository,
        mock_embedding_service,
        mock_llm_service,
    ):
        """Пирамида нот из LLM включается в результат."""
        mock_perfume_repository.search_by_embedding.return_value = []
        use_case = self._make_use_case(
            mock_perfume_repository, mock_embedding_service, mock_llm_service
        )

        result = use_case.execute(query="древесный мускус", limit=5)

        assert result.note_pyramid is not None
        assert len(result.note_pyramid.top) > 0 or len(result.note_pyramid.base) > 0

    def test_cache_miss_calls_services_and_writes_to_cache(
        self,
        mock_perfume_repository,
        mock_embedding_service,
        mock_llm_service,
    ):
        """Промах кэша: сервисы вызываются, результат записывается в кэш."""
        mock_perfume_repository.search_by_embedding.return_value = []
        mock_cache = MagicMock(spec=ICacheService)
        mock_cache.get.return_value = None

        use_case = self._make_use_case(
            mock_perfume_repository, mock_embedding_service, mock_llm_service, cache=mock_cache
        )
        use_case.execute(query="летний цветочный", limit=5)

        mock_cache.get.assert_called_once()
        mock_embedding_service.generate_embedding.assert_called_once()
        mock_llm_service.generate_search_result.assert_called_once()
        mock_cache.set.assert_called_once()

    def test_cache_hit_skips_services(
        self,
        mock_perfume_repository,
        mock_embedding_service,
        mock_llm_service,
        mock_llm_service_result,
    ):
        """Попадание в кэш: эмбеддинг и LLM не вызываются."""
        mock_cache = MagicMock(spec=ICacheService)
        mock_cache.get.return_value = mock_llm_service_result

        use_case = self._make_use_case(
            mock_perfume_repository, mock_embedding_service, mock_llm_service, cache=mock_cache
        )
        result = use_case.execute(query="летний цветочный", limit=5)

        mock_embedding_service.generate_embedding.assert_not_called()
        mock_llm_service.generate_search_result.assert_not_called()
        mock_perfume_repository.search_by_embedding.assert_not_called()
        assert isinstance(result, SearchResult)

    def test_cache_key_is_query_based(
        self,
        mock_perfume_repository,
        mock_embedding_service,
        mock_llm_service,
    ):
        """Одинаковый запрос даёт одинаковый ключ кэша (общий кэш для всех пользователей)."""
        mock_perfume_repository.search_by_embedding.return_value = []
        mock_cache = MagicMock(spec=ICacheService)
        mock_cache.get.return_value = None

        use_case = self._make_use_case(
            mock_perfume_repository, mock_embedding_service, mock_llm_service, cache=mock_cache
        )

        use_case.execute(query="тест", limit=5)
        use_case.execute(query="тест", limit=5)

        keys_used = [call.args[0] for call in mock_cache.get.call_args_list]
        assert keys_used[0] == keys_used[1], "Одинаковый запрос должен давать одинаковый ключ кэша"

    def test_cache_hit_serves_second_request(
        self,
        mock_perfume_repository,
        mock_embedding_service,
        mock_llm_service,
        mock_llm_service_result,
    ):
        """Второй запрос получает результат из кэша, созданного первым."""
        mock_cache = MagicMock(spec=ICacheService)
        mock_cache.get.side_effect = [None, mock_llm_service_result]

        use_case = self._make_use_case(
            mock_perfume_repository, mock_embedding_service, mock_llm_service, cache=mock_cache
        )

        mock_perfume_repository.search_by_embedding.return_value = []
        use_case.execute(query="общий запрос", limit=5)
        use_case.execute(query="общий запрос", limit=5)

        assert mock_embedding_service.generate_embedding.call_count == 1
        assert mock_llm_service.generate_search_result.call_count == 1


class TestFindSimilarUseCase:

    def test_find_similar_returns_results(
        self, mock_perfume_repository, sample_perfume, sample_perfumes
    ):
        """Похожие ароматы — возвращает список с релевантностью."""
        mock_perfume_repository.get_by_id.return_value = sample_perfume
        mock_perfume_repository.find_similar.return_value = [
            (p, 0.9 - i * 0.1) for i, p in enumerate(sample_perfumes[:3])
        ]
        use_case = FindSimilarUseCase(perfume_repository=mock_perfume_repository)

        results = use_case.execute(perfume_id=1, limit=3)

        assert len(results) == 3
        assert all(isinstance(r, PerfumeWithRelevance) for r in results)
        mock_perfume_repository.find_similar.assert_called_once_with(
            perfume_id=1, limit=3
        )

    def test_find_similar_nonexistent_perfume_raises(self, mock_perfume_repository):
        """Несуществующий аромат — PerfumeNotFoundError, find_similar не вызывается."""
        mock_perfume_repository.get_by_id.return_value = None
        use_case = FindSimilarUseCase(perfume_repository=mock_perfume_repository)

        with pytest.raises(PerfumeNotFoundError):
            use_case.execute(perfume_id=99999, limit=5)

        mock_perfume_repository.find_similar.assert_not_called()

    def test_find_similar_respects_limit(
        self, mock_perfume_repository, sample_perfume
    ):
        """Параметр limit передаётся в репозиторий."""
        mock_perfume_repository.get_by_id.return_value = sample_perfume
        mock_perfume_repository.find_similar.return_value = []
        use_case = FindSimilarUseCase(perfume_repository=mock_perfume_repository)

        use_case.execute(perfume_id=1, limit=7)

        mock_perfume_repository.find_similar.assert_called_once_with(
            perfume_id=1, limit=7
        )
