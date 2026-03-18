"""
API эндпоинты для работы с ароматами.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas.perfume import (
    PerfumeResponse,
    PerfumeNoteResponse,
    PerfumeTagResponse,
    Note,
    FiltersResponse,
)
from app.api.dependencies import (
    get_perfume_use_case,
    get_filters_use_case,
    get_brands_use_case,
)
from app.core.use_cases import GetPerfumeUseCase, GetFiltersUseCase, GetBrandsUseCase
from app.core.exceptions import PerfumeNotFoundError

router = APIRouter()


def _perfume_to_response(perfume) -> PerfumeResponse:
    """Конвертировать доменную сущность в API схему."""
    notes = [
        PerfumeNoteResponse(
            note=Note(
                id=pn.note.id,
                name=pn.note.name,
                category=pn.note.category,
            ),
            level=pn.level,
        )
        for pn in perfume.notes
    ]

    tags = [
        PerfumeTagResponse(
            tag=t.tag,
            confidence=t.confidence,
            source=t.source,
        )
        for t in perfume.tags
    ]

    return PerfumeResponse(
        id=perfume.id,
        name=perfume.name,
        brand=perfume.brand,
        year=perfume.year,
        product_type=perfume.product_type,
        family=perfume.family,
        gender=perfume.gender,
        description=perfume.description,
        image_url=perfume.image_url,
        source_url=perfume.source_url,
        notes=notes,
        tags=tags,
        created_at=perfume.created_at,
        updated_at=perfume.updated_at,
    )


@router.get("/filters/all", response_model=FiltersResponse)
async def get_filters(
    use_case: GetFiltersUseCase = Depends(get_filters_use_case),
):
    """
    Получить доступные значения для всех фильтров.
    """
    filters = use_case.execute()
    return FiltersResponse(
        genders=filters.genders,
        families=filters.families,
        product_types=filters.product_types,
        brands=filters.brands,
        notes=filters.notes,
    )


@router.get("/brands/all", response_model=list[str])
async def get_brands(
    use_case: GetBrandsUseCase = Depends(get_brands_use_case),
):
    """
    Получить список всех брендов, отсортированный по алфавиту.
    """
    return use_case.execute()


@router.get("/{perfume_id}", response_model=PerfumeResponse)
async def get_perfume(
    perfume_id: int,
    use_case: GetPerfumeUseCase = Depends(get_perfume_use_case),
):
    """
    Получить детальную информацию об аромате.

    - **perfume_id**: ID аромата
    """
    try:
        perfume = use_case.execute(perfume_id)
        return _perfume_to_response(perfume)
    except PerfumeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Perfume with id={perfume_id} not found",
        )
