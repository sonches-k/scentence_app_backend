import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

from app.api.converters import perfume_with_relevance_to_response
from app.api.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchFilters,
    SimilarSearchResponse,
)
from app.api.schemas.perfume import NotePyramid
from app.api.dependencies import (
    get_semantic_search_use_case,
    get_find_similar_use_case,
    get_user_repository,
    get_optional_current_user,
)
from app.core.entities import User
from app.core.exceptions import LLMTimeoutError, PerfumeNotFoundError
from app.core.interfaces import IUserRepository
from app.core.use_cases import SemanticSearchUseCase, FindSimilarUseCase
from app.core.value_objects import SearchFilters as UseCaseSearchFilters

router = APIRouter()


def _convert_filters(filters: SearchFilters | None) -> UseCaseSearchFilters | None:
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


@router.post("/", response_model=SearchResponse, status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
async def semantic_search(
    request: Request,
    body: SearchRequest,
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

    Если внешний LLM-сервис не отвечает в пределах таймаута (60 секунд),
    обработка прерывается и клиент получает HTTP 504 Gateway Timeout
    (см. требование ТЗ п. 3.14).
    """
    filters = _convert_filters(body.filters)
    try:
        result = use_case.execute(
            query=body.query,
            filters=filters,
            limit=body.limit,
        )
    except LLMTimeoutError as exc:
        logger.warning("LLM timeout during semantic search: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM service did not respond in time. Please try again later.",
        ) from exc

    if current_user:
        try:
            user_repo.add_search_history(
                user_id=current_user.id,
                query_text=body.query,
                filters=result.filters_applied,
            )
        except Exception as e:
            logger.error("Failed to save search history for user %s: %s", current_user.id, e)

    perfumes_response = [perfume_with_relevance_to_response(p) for p in result.perfumes]

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
    limit: int = Query(5, ge=1, le=20, description="Количество похожих ароматов (1–20)"),
    use_case: FindSimilarUseCase = Depends(get_find_similar_use_case),
):
    try:
        results = use_case.execute(perfume_id=perfume_id, limit=limit)
    except PerfumeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfume not found",
        )

    perfumes_response = [perfume_with_relevance_to_response(p) for p in results]

    return SimilarSearchResponse(
        source_perfume_id=perfume_id,
        similar_perfumes=perfumes_response,
    )
