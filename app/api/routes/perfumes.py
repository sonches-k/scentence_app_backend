import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

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
    get_suggest_brands_use_case,
    get_suggest_notes_use_case,
)
from app.core.use_cases import GetPerfumeUseCase, GetFiltersUseCase, SuggestBrandsUseCase, SuggestNotesUseCase
from app.core.exceptions import PerfumeNotFoundError

router = APIRouter()


def _perfume_to_response(perfume) -> PerfumeResponse:
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


def _compute_etag(data: dict | list) -> str:
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(payload.encode()).hexdigest()


@router.get("/filters", response_model=FiltersResponse)
async def get_filters(
    request: Request,
    response: Response,
    use_case: GetFiltersUseCase = Depends(get_filters_use_case),
):
    filters = use_case.execute()
    data = {
        "genders": filters.genders,
        "families": filters.families,
        "product_types": filters.product_types,
        "categories": filters.categories,
    }
    etag = _compute_etag(data)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"
    return FiltersResponse(**data)


@router.get("/brands/suggest", response_model=list[str])
async def suggest_brands(
    q: str = "",
    limit: int = 20,
    use_case: SuggestBrandsUseCase = Depends(get_suggest_brands_use_case),
):
    return use_case.execute(q=q.strip(), limit=limit)


@router.get("/notes/suggest", response_model=list[str])
async def suggest_notes(
    q: str = "",
    limit: int = 20,
    use_case: SuggestNotesUseCase = Depends(get_suggest_notes_use_case),
):
    return use_case.execute(q=q.strip(), limit=limit)


@router.get("/{perfume_id}", response_model=PerfumeResponse)
async def get_perfume(
    perfume_id: int,
    use_case: GetPerfumeUseCase = Depends(get_perfume_use_case),
):
    try:
        perfume = use_case.execute(perfume_id)
        return _perfume_to_response(perfume)
    except PerfumeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Perfume with id={perfume_id} not found",
        )
