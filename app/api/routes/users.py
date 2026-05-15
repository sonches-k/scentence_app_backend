from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.converters import perfume_to_card
from app.api.schemas.perfume import PerfumeCard
from app.api.schemas.auth import ProfileResponse, UpdateProfileRequest
from app.api.dependencies import (
    get_update_profile_use_case,
    get_favorites_use_case,
    get_add_favorite_use_case,
    get_remove_favorite_use_case,
    get_search_history_use_case,
    get_delete_search_history_entry_use_case,
    get_clear_search_history_use_case,
    get_current_user,
)
from app.core.entities import User
from app.core.use_cases import (
    UpdateProfileUseCase,
    GetFavoritesUseCase,
    AddFavoriteUseCase,
    RemoveFavoriteUseCase,
    GetSearchHistoryUseCase,
    DeleteSearchHistoryEntryUseCase,
    ClearSearchHistoryUseCase,
)
from app.core.exceptions import PerfumeNotFoundError, UserNotFoundError

router = APIRouter()


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
):
    return ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
    )


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    use_case: UpdateProfileUseCase = Depends(get_update_profile_use_case),
):
    updated = use_case.execute(current_user.id, request.name)
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
    try:
        perfumes = use_case.execute(current_user.id)
        return [perfume_to_card(p) for p in perfumes]
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
    """
    Добавить аромат в избранное.

    Возвращает 404, если запрошенный аромат не существует.
    Операция идемпотентна: повторный вызов для уже добавленного аромата
    возвращает существующую запись избранного.
    """
    try:
        favorite = use_case.execute(current_user.id, perfume_id)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    except PerfumeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfume not found",
        )
    return {"message": "Added to favorites", "id": favorite.id}


@router.delete("/favorites/{perfume_id}")
async def remove_favorite(
    perfume_id: int,
    use_case: RemoveFavoriteUseCase = Depends(get_remove_favorite_use_case),
    current_user: User = Depends(get_current_user),
):
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
    limit: int = Query(default=100, ge=1, le=200),
):
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


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    use_case: ClearSearchHistoryUseCase = Depends(get_clear_search_history_use_case),
    current_user: User = Depends(get_current_user),
):
    use_case.execute(current_user.id)


@router.delete("/history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_entry(
    entry_id: int,
    use_case: DeleteSearchHistoryEntryUseCase = Depends(get_delete_search_history_entry_use_case),
    current_user: User = Depends(get_current_user),
):
    deleted = use_case.execute(user_id=current_user.id, entry_id=entry_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History entry not found",
        )
