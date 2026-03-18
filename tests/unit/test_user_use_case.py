"""
Unit-тесты для user use cases.
"""

import pytest

from app.core.entities import User, UserFavorite
from app.core.exceptions import UserNotFoundError
from app.core.use_cases.user import (
    GetFavoritesUseCase,
    AddFavoriteUseCase,
    RemoveFavoriteUseCase,
    GetSearchHistoryUseCase,
)


pytestmark = pytest.mark.unit


class TestGetFavoritesUseCase:

    def test_get_favorites_returns_list(
        self, mock_user_repository, sample_user, sample_perfumes
    ):
        """Возвращает список избранных ароматов пользователя."""
        mock_user_repository.get_by_id.return_value = sample_user
        mock_user_repository.get_favorites.return_value = sample_perfumes[:2]

        use_case = GetFavoritesUseCase(user_repository=mock_user_repository)
        result = use_case.execute(user_id=1)

        assert len(result) == 2
        mock_user_repository.get_by_id.assert_called_once_with(1)
        mock_user_repository.get_favorites.assert_called_once_with(1)

    def test_get_favorites_user_not_found(self, mock_user_repository):
        """Несуществующий пользователь — бросает UserNotFoundError."""
        mock_user_repository.get_by_id.return_value = None

        use_case = GetFavoritesUseCase(user_repository=mock_user_repository)

        with pytest.raises(UserNotFoundError):
            use_case.execute(user_id=99999)

    def test_get_favorites_empty(self, mock_user_repository, sample_user):
        """Нет избранного — возвращает пустой список."""
        mock_user_repository.get_by_id.return_value = sample_user
        mock_user_repository.get_favorites.return_value = []

        use_case = GetFavoritesUseCase(user_repository=mock_user_repository)
        result = use_case.execute(user_id=1)

        assert result == []


class TestAddFavoriteUseCase:

    def test_add_favorite_success(
        self, mock_user_repository, mock_perfume_repository, sample_user
    ):
        """Добавление в избранное — возвращает UserFavorite."""
        mock_user_repository.get_by_id.return_value = sample_user
        mock_user_repository.is_favorite.return_value = False
        expected = UserFavorite(id=1, user_id=1, perfume_id=10)
        mock_user_repository.add_favorite.return_value = expected

        use_case = AddFavoriteUseCase(
            user_repository=mock_user_repository,
            perfume_repository=mock_perfume_repository,
        )
        result = use_case.execute(user_id=1, perfume_id=10)

        assert result.user_id == 1
        assert result.perfume_id == 10
        mock_user_repository.add_favorite.assert_called_once_with(1, 10)

    def test_add_favorite_user_not_found(
        self, mock_user_repository, mock_perfume_repository
    ):
        """Несуществующий пользователь — бросает UserNotFoundError."""
        mock_user_repository.get_by_id.return_value = None

        use_case = AddFavoriteUseCase(
            user_repository=mock_user_repository,
            perfume_repository=mock_perfume_repository,
        )

        with pytest.raises(UserNotFoundError):
            use_case.execute(user_id=99999, perfume_id=1)

    def test_add_favorite_already_exists(
        self, mock_user_repository, mock_perfume_repository, sample_user, sample_perfume
    ):
        """Аромат уже в избранном — не добавляет дубликат."""
        mock_user_repository.get_by_id.return_value = sample_user
        mock_user_repository.is_favorite.return_value = True
        mock_user_repository.get_favorites.return_value = [sample_perfume]

        use_case = AddFavoriteUseCase(
            user_repository=mock_user_repository,
            perfume_repository=mock_perfume_repository,
        )
        use_case.execute(user_id=1, perfume_id=1)

        mock_user_repository.add_favorite.assert_not_called()


class TestRemoveFavoriteUseCase:

    def test_remove_favorite_success(self, mock_user_repository, sample_user):
        """Удаление из избранного — возвращает True."""
        mock_user_repository.get_by_id.return_value = sample_user
        mock_user_repository.remove_favorite.return_value = True

        use_case = RemoveFavoriteUseCase(user_repository=mock_user_repository)
        result = use_case.execute(user_id=1, perfume_id=10)

        assert result is True
        mock_user_repository.remove_favorite.assert_called_once_with(1, 10)

    def test_remove_favorite_not_in_list(self, mock_user_repository, sample_user):
        """Аромат не в избранном — возвращает False."""
        mock_user_repository.get_by_id.return_value = sample_user
        mock_user_repository.remove_favorite.return_value = False

        use_case = RemoveFavoriteUseCase(user_repository=mock_user_repository)
        result = use_case.execute(user_id=1, perfume_id=99)

        assert result is False

    def test_remove_favorite_user_not_found(self, mock_user_repository):
        """Несуществующий пользователь — бросает UserNotFoundError."""
        mock_user_repository.get_by_id.return_value = None

        use_case = RemoveFavoriteUseCase(user_repository=mock_user_repository)

        with pytest.raises(UserNotFoundError):
            use_case.execute(user_id=99999, perfume_id=1)


class TestGetSearchHistoryUseCase:

    def test_get_history_returns_list(self, mock_user_repository, sample_user):
        """Возвращает историю поиска пользователя."""
        from app.core.entities import SearchHistoryEntry
        from datetime import datetime

        mock_user_repository.get_by_id.return_value = sample_user
        history = [
            SearchHistoryEntry(id=i, user_id=1, query_text=f"запрос {i}", created_at=datetime.now())
            for i in range(1, 4)
        ]
        mock_user_repository.get_search_history.return_value = history

        use_case = GetSearchHistoryUseCase(user_repository=mock_user_repository)
        result = use_case.execute(user_id=1, limit=10)

        assert len(result) == 3
        mock_user_repository.get_search_history.assert_called_once_with(1, 10)

    def test_get_history_user_not_found(self, mock_user_repository):
        """Несуществующий пользователь — бросает UserNotFoundError."""
        mock_user_repository.get_by_id.return_value = None

        use_case = GetSearchHistoryUseCase(user_repository=mock_user_repository)

        with pytest.raises(UserNotFoundError):
            use_case.execute(user_id=99999)
