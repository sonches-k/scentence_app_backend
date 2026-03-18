"""
Unit-тесты для SemanticSearchUseCase и FindSimilarUseCase.
"""

import pytest

from app.core.entities.perfume import PerfumeWithRelevance
from app.core.use_cases.search import SemanticSearchUseCase, FindSimilarUseCase, SearchResult
from app.core.value_objects import SearchFilters


pytestmark = pytest.mark.unit


class TestSemanticSearchUseCase:

    def _make_use_case(self, perfume_repo, embedding_service, llm_service):
        return SemanticSearchUseCase(
            perfume_repository=perfume_repo,
            embedding_service=embedding_service,
            llm_service=llm_service,
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
        mock_llm_service.extract_note_pyramid.assert_called_once()
        mock_llm_service.generate_search_explanation.assert_called_once()

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


class TestFindSimilarUseCase:

    def test_find_similar_returns_results(
        self, mock_perfume_repository, sample_perfumes
    ):
        """Похожие ароматы — возвращает список с релевантностью."""
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

    def test_find_similar_invalid_id_returns_empty(self, mock_perfume_repository):
        """Несуществующий ID — возвращает пустой список (без ошибки)."""
        mock_perfume_repository.find_similar.return_value = []
        use_case = FindSimilarUseCase(perfume_repository=mock_perfume_repository)

        results = use_case.execute(perfume_id=99999, limit=5)

        assert results == []

    def test_find_similar_respects_limit(self, mock_perfume_repository, sample_perfumes):
        """Параметр limit передаётся в репозиторий."""
        mock_perfume_repository.find_similar.return_value = []
        use_case = FindSimilarUseCase(perfume_repository=mock_perfume_repository)

        use_case.execute(perfume_id=1, limit=7)

        mock_perfume_repository.find_similar.assert_called_once_with(
            perfume_id=1, limit=7
        )
