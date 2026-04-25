from typing import Optional

from app.core.entities import Perfume, UserFavorite, SearchHistoryEntry
from app.core.exceptions import UserNotFoundError
from app.core.interfaces import IUserRepository, IPerfumeRepository


class GetFavoritesUseCase:

    def __init__(self, user_repository: IUserRepository):
        self._user_repo = user_repository

    def execute(self, user_id: int) -> list[Perfume]:
        user = self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id={user_id} not found")
        return self._user_repo.get_favorites(user_id)


class AddFavoriteUseCase:

    def __init__(
        self,
        user_repository: IUserRepository,
        perfume_repository: IPerfumeRepository,
    ):
        self._user_repo = user_repository
        self._perfume_repo = perfume_repository

    def execute(self, user_id: int, perfume_id: int) -> UserFavorite:
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

    def __init__(self, user_repository: IUserRepository):
        self._user_repo = user_repository

    def execute(self, user_id: int, perfume_id: int) -> bool:
        user = self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id={user_id} not found")
        return self._user_repo.remove_favorite(user_id, perfume_id)


class GetSearchHistoryUseCase:

    def __init__(self, user_repository: IUserRepository):
        self._user_repo = user_repository

    def execute(self, user_id: int, limit: int = 100) -> list[SearchHistoryEntry]:
        user = self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id={user_id} not found")
        return self._user_repo.get_search_history(user_id, limit)


class DeleteSearchHistoryEntryUseCase:

    def __init__(self, user_repository: IUserRepository):
        self._user_repo = user_repository

    def execute(self, user_id: int, entry_id: int) -> bool:
        return self._user_repo.delete_search_history_entry(entry_id=entry_id, user_id=user_id)


class ClearSearchHistoryUseCase:

    def __init__(self, user_repository: IUserRepository):
        self._user_repo = user_repository

    def execute(self, user_id: int) -> None:
        self._user_repo.delete_all_search_history(user_id)
