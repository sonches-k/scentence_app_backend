"""
API эндпоинты для работы с пользователями.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas.perfume import PerfumeCard
from app.api.schemas.auth import ProfileResponse, UpdateProfileRequest
from app.api.dependencies import (
    get_favorites_use_case,
    get_add_favorite_use_case,
    get_remove_favorite_use_case,
    get_search_history_use_case,
    get_user_repository,
    get_current_user,
)
from app.core.entities import User
from app.core.interfaces import IUserRepository
from app.core.use_cases import (
    GetFavoritesUseCase,
    AddFavoriteUseCase,
    RemoveFavoriteUseCase,
    GetSearchHistoryUseCase,
)
from app.core.exceptions import UserNotFoundError

router = APIRouter()


def _perfume_to_card(perfume) -> PerfumeCard:
    """Конвертировать доменную сущность в карточку."""
    top_notes = [pn.note.name for pn in perfume.notes if pn.level.lower() == "top"][:5]
    middle_notes = [pn.note.name for pn in perfume.notes if pn.level.lower() == "middle"][:5]
    base_notes = [pn.note.name for pn in perfume.notes if pn.level.lower() == "base"][:5]

    return PerfumeCard(
        id=perfume.id,
        name=perfume.name,
        brand=perfume.brand,
        image_url=perfume.image_url,
        source_url=perfume.source_url,
        family=perfume.family,
        gender=perfume.gender,
        top_notes=top_notes,
        middle_notes=middle_notes,
        base_notes=base_notes,
    )


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
):
    """Получить профиль текущего пользователя."""
    return ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
    )


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    user_repo: IUserRepository = Depends(get_user_repository),
):
    """Обновить имя пользователя (2–50 символов)."""
    updated = user_repo.update_name(current_user.id, request.name)
    return ProfileResponse(
        id=updated.id,
        email=updated.email,
        name=updated.name,
    )


@router.get("/favorites", response_model=list[PerfumeCard])
async def get_favorites(
    use_case: GetFavoritesUseCase = Depends(get_favorites_use_case),
    current_user: User = Depends(get_current_user),
):
    """Получить список избранных ароматов пользователя."""
    try:
        perfumes = use_case.execute(current_user.id)
        return [_perfume_to_card(p) for p in perfumes]
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


@router.post("/favorites/{perfume_id}", status_code=status.HTTP_201_CREATED)
async def add_favorite(
    perfume_id: int,
    use_case: AddFavoriteUseCase = Depends(get_add_favorite_use_case),
    current_user: User = Depends(get_current_user),
):
    """Добавить аромат в избранное."""
    try:
        favorite = use_case.execute(current_user.id, perfume_id)
        return {"message": "Added to favorites", "id": favorite.id}
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


@router.delete("/favorites/{perfume_id}")
async def remove_favorite(
    perfume_id: int,
    use_case: RemoveFavoriteUseCase = Depends(get_remove_favorite_use_case),
    current_user: User = Depends(get_current_user),
):
    """Удалить аромат из избранного."""
    try:
        removed = use_case.execute(current_user.id, perfume_id)
        if removed:
            return {"message": "Removed from favorites"}
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found",
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


@router.get("/history")
async def get_history(
    use_case: GetSearchHistoryUseCase = Depends(get_search_history_use_case),
    current_user: User = Depends(get_current_user),
    limit: int = 100,
):
    """Получить историю поиска пользователя."""
    try:
        history = use_case.execute(current_user.id, limit)
        return [
            {
                "id": h.id,
                "query": h.query_text,
                "filters": h.filters,
                "created_at": h.created_at,
            }
            for h in history
        ]
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
