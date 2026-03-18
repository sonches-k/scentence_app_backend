"""
Use Cases для работы с пользователями.
"""

from typing import Optional

from app.core.entities import Perfume, UserFavorite, SearchHistoryEntry
from app.core.exceptions import UserNotFoundError
from app.core.interfaces import IUserRepository, IPerfumeRepository


class GetFavoritesUseCase:
    """
    Use Case: Получение избранных ароматов.
    """

    def __init__(self, user_repository: IUserRepository):
        self._user_repo = user_repository

    def execute(self, user_id: int) -> list[Perfume]:
        """Получить избранные ароматы пользователя."""
        user = self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id={user_id} not found")
        return self._user_repo.get_favorites(user_id)


class AddFavoriteUseCase:
    """
    Use Case: Добавление аромата в избранное.
    """

    def __init__(
        self,
        user_repository: IUserRepository,
        perfume_repository: IPerfumeRepository,
    ):
        self._user_repo = user_repository
        self._perfume_repo = perfume_repository

    def execute(self, user_id: int, perfume_id: int) -> UserFavorite:
        """Добавить аромат в избранное."""
        user = self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id={user_id} not found")

        if self._user_repo.is_favorite(user_id, perfume_id):
            favorites = self._user_repo.get_favorites(user_id)
            for fav in favorites:
                if fav.id == perfume_id:
                    return UserFavorite(
                        id=0,
                        user_id=user_id,
                        perfume_id=perfume_id,
                    )

        return self._user_repo.add_favorite(user_id, perfume_id)


class RemoveFavoriteUseCase:
    """
    Use Case: Удаление аромата из избранного.
    """

    def __init__(self, user_repository: IUserRepository):
        self._user_repo = user_repository

    def execute(self, user_id: int, perfume_id: int) -> bool:
        """Удалить аромат из избранного."""
        user = self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id={user_id} not found")
        return self._user_repo.remove_favorite(user_id, perfume_id)


class GetSearchHistoryUseCase:
    """
    Use Case: Получение истории поиска.
    """

    def __init__(self, user_repository: IUserRepository):
        self._user_repo = user_repository

    def execute(self, user_id: int, limit: int = 100) -> list[SearchHistoryEntry]:
        """Получить историю поиска пользователя."""
        user = self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id={user_id} not found")
        return self._user_repo.get_search_history(user_id, limit)
