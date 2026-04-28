"""
Unit-тесты для GetPerfumeUseCase и GetFiltersUseCase.
"""

import pytest

from app.core.exceptions import PerfumeNotFoundError
from app.core.use_cases.perfume import (
    GetPerfumeUseCase,
    GetFiltersUseCase,
    FiltersData,
)


pytestmark = pytest.mark.unit


class TestGetPerfumeUseCase:

    def test_get_perfume_exists(self, mock_perfume_repository, sample_perfume):
        """Существующий ID — возвращает полный объект Perfume."""
        mock_perfume_repository.get_by_id.return_value = sample_perfume
        use_case = GetPerfumeUseCase(perfume_repository=mock_perfume_repository)

        result = use_case.execute(perfume_id=1)

        assert result.id == 1
        assert result.name == "Chanel No. 5"
        assert result.brand == "Chanel"
        assert len(result.notes) == 3
        mock_perfume_repository.get_by_id.assert_called_once_with(1)

    def test_get_perfume_not_found(self, mock_perfume_repository):
        """Несуществующий ID — бросает PerfumeNotFoundError."""
        mock_perfume_repository.get_by_id.return_value = None
        use_case = GetPerfumeUseCase(perfume_repository=mock_perfume_repository)

        with pytest.raises(PerfumeNotFoundError):
            use_case.execute(perfume_id=99999)

    def test_get_perfume_calls_repo_with_correct_id(
        self, mock_perfume_repository, sample_perfume
    ):
        """Репозиторий вызывается с переданным ID."""
        mock_perfume_repository.get_by_id.return_value = sample_perfume
        use_case = GetPerfumeUseCase(perfume_repository=mock_perfume_repository)

        use_case.execute(perfume_id=42)

        mock_perfume_repository.get_by_id.assert_called_once_with(42)


class TestGetFiltersUseCase:

    def test_get_filters_returns_all_fields(self, mock_perfume_repository):
        """Возвращает FiltersData со всеми полями."""
        mock_perfume_repository.get_unique_genders.return_value       = ["Female", "Male", "Unisex"]
        mock_perfume_repository.get_unique_families.return_value      = ["Floral", "Oriental", "Woody"]
        mock_perfume_repository.get_unique_product_types.return_value = ["EDP", "EDT"]
        mock_perfume_repository.get_unique_categories.return_value    = ["Люкс", "Нишевая"]

        use_case = GetFiltersUseCase(perfume_repository=mock_perfume_repository)
        result = use_case.execute()

        assert isinstance(result, FiltersData)
        assert result.genders == ["Female", "Male", "Unisex"]
        assert result.families == ["Floral", "Oriental", "Woody"]
        assert result.product_types == ["EDP", "EDT"]
        assert result.categories == ["Люкс", "Нишевая"]

    def test_get_filters_calls_repo_methods(self, mock_perfume_repository):
        """Вызываются нужные методы репозитория для получения фильтров."""
        mock_perfume_repository.get_unique_genders.return_value       = []
        mock_perfume_repository.get_unique_families.return_value      = []
        mock_perfume_repository.get_unique_product_types.return_value = []
        mock_perfume_repository.get_unique_categories.return_value    = []

        use_case = GetFiltersUseCase(perfume_repository=mock_perfume_repository)
        use_case.execute()

        mock_perfume_repository.get_unique_genders.assert_called_once()
        mock_perfume_repository.get_unique_families.assert_called_once()
        mock_perfume_repository.get_unique_product_types.assert_called_once()
        mock_perfume_repository.get_unique_categories.assert_called_once()

    def test_get_filters_empty_db(self, mock_perfume_repository):
        """Пустая БД — возвращает FiltersData с пустыми списками."""
        mock_perfume_repository.get_unique_genders.return_value       = []
        mock_perfume_repository.get_unique_families.return_value      = []
        mock_perfume_repository.get_unique_product_types.return_value = []
        mock_perfume_repository.get_unique_categories.return_value    = []

        use_case = GetFiltersUseCase(perfume_repository=mock_perfume_repository)
        result = use_case.execute()

        assert result.genders == []
        assert result.categories == []
