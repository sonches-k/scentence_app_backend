"""
Pydantic schemas для API.
"""

from app.api.schemas.perfume import (
    Note,
    NotePyramid,
    PerfumeNoteResponse,
    PerfumeTagResponse,
    PerfumeResponse,
    PerfumeCard,
    PerfumeWithRelevance,
    FiltersResponse,
)
from app.api.schemas.search import (
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SimilarSearchResponse,
)

__all__ = [
    "Note",
    "NotePyramid",
    "PerfumeNoteResponse",
    "PerfumeTagResponse",
    "PerfumeResponse",
    "PerfumeCard",
    "PerfumeWithRelevance",
    "FiltersResponse",
    "SearchFilters",
    "SearchRequest",
    "SearchResponse",
    "SimilarSearchResponse",
]
