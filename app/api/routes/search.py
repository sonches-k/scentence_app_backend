"""
API эндпоинты для поиска ароматов.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, status

logger = logging.getLogger(__name__)

from app.api.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchFilters,
    SimilarSearchResponse,
)
from app.api.schemas.perfume import NotePyramid, PerfumeWithRelevance
from app.api.dependencies import (
    get_semantic_search_use_case,
    get_find_similar_use_case,
    get_user_repository,
    get_optional_current_user,
)
from app.core.entities import User
from app.core.interfaces import IUserRepository
from app.core.use_cases import SemanticSearchUseCase, FindSimilarUseCase
from app.core.value_objects import SearchFilters as UseCaseSearchFilters

router = APIRouter()


def _convert_filters(filters: SearchFilters | None) -> UseCaseSearchFilters | None:
    """Конвертировать API фильтры в use case фильтры."""
    if not filters:
        return None
    return UseCaseSearchFilters.from_lists(
        genders=filters.genders,
        families=filters.families,
        product_types=filters.product_types,
        brands=filters.brands,
        notes=filters.notes,
        year_from=filters.year_from,
        year_to=filters.year_to,
    )


def _perfume_to_response(perfume_with_rel) -> PerfumeWithRelevance:
    """Конвертировать доменную сущность в API схему."""
    perfume = perfume_with_rel.perfume
    top_notes = [pn.note.name for pn in perfume.notes if pn.level.lower() == "top"][:5]
    middle_notes = [pn.note.name for pn in perfume.notes if pn.level.lower() == "middle"][:5]
    base_notes = [pn.note.name for pn in perfume.notes if pn.level.lower() == "base"][:5]

    return PerfumeWithRelevance(
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
        relevance=perfume_with_rel.relevance,
    )


@router.post("/", response_model=SearchResponse, status_code=status.HTTP_200_OK)
async def semantic_search(
    request: SearchRequest,
    use_case: SemanticSearchUseCase = Depends(get_semantic_search_use_case),
    current_user: Optional[User] = Depends(get_optional_current_user),
    user_repo: IUserRepository = Depends(get_user_repository),
):
    """
    Семантический поиск ароматов по текстовому описанию.

    - **query**: Текстовое описание желаемого аромата (3-1000 символов)
    - **filters**: Опциональные фильтры для уточнения результатов
    - **limit**: Количество результатов (1-20, по умолчанию 5)

    Если передан Bearer токен — запрос сохраняется в историю.
    """
    filters = _convert_filters(request.filters)
    result = use_case.execute(
        query=request.query,
        filters=filters,
        limit=request.limit,
    )

    if current_user:
        try:
            user_repo.add_search_history(
                user_id=current_user.id,
                query_text=request.query,
                filters=result.filters_applied,
            )
        except Exception as e:
            logger.error("Failed to save search history for user %s: %s", current_user.id, e)

    perfumes_response = [_perfume_to_response(p) for p in result.perfumes]

    return SearchResponse(
        query=result.query,
        note_pyramid=NotePyramid(
            top=result.note_pyramid.top,
            middle=result.note_pyramid.middle,
            base=result.note_pyramid.base,
        ),
        explanation=result.explanation,
        perfumes=perfumes_response,
        filters_applied=result.filters_applied,
        total_found=result.total_found,
    )


@router.post("/similar/{perfume_id}", response_model=SimilarSearchResponse)
async def find_similar(
    perfume_id: int,
    limit: int = 5,
    use_case: FindSimilarUseCase = Depends(get_find_similar_use_case),
):
    """
    Поиск похожих ароматов на основе векторного сходства.

    - **perfume_id**: ID аромата, к которому ищем похожие
    - **limit**: Количество результатов (1-20, по умолчанию 5)
    """
    results = use_case.execute(perfume_id=perfume_id, limit=limit)
    perfumes_response = [_perfume_to_response(p) for p in results]

    return SimilarSearchResponse(
        source_perfume_id=perfume_id,
        similar_perfumes=perfumes_response,
    )
