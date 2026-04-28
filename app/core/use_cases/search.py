import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.core.entities import NotePyramid, PerfumeWithRelevance
from app.core.exceptions import PerfumeNotFoundError
from app.core.value_objects import SearchFilters
from app.core.interfaces import (
    IPerfumeRepository,
    IEmbeddingService,
    ILLMService,
    ICacheService,
)
from app.core.use_cases.perfume import perfume_to_dict, perfume_from_dict

_CACHE_TTL = 180 * 24 * 3600  # 180 дней


def normalize_query(query: str) -> str:
    """Нормализация поискового запроса перед векторизацией.

    - Unicode NFC: унифицирует представление символов (важно для кириллицы)
    - lower: регистронезависимый поиск
    - collapse whitespace: множественные пробелы → один
    - strip: убирает пробелы по краям
    """
    query = unicodedata.normalize("NFC", query)
    query = query.lower()
    query = re.sub(r"\s+", " ", query)
    return query.strip()


@dataclass
class SearchResult:
    query: str
    note_pyramid: NotePyramid
    explanation: str
    perfumes: list[PerfumeWithRelevance]
    filters_applied: Optional[dict]
    total_found: int


def _search_result_to_dict(r: SearchResult) -> dict:
    return {
        "query": r.query,
        "note_pyramid": {
            "top": list(r.note_pyramid.top),
            "middle": list(r.note_pyramid.middle),
            "base": list(r.note_pyramid.base),
        },
        "explanation": r.explanation,
        "perfumes": [
            {"perfume": perfume_to_dict(p.perfume), "relevance": p.relevance}
            for p in r.perfumes
        ],
        "filters_applied": r.filters_applied,
        "total_found": r.total_found,
    }


def _search_result_from_dict(d: dict) -> SearchResult:
    np = d["note_pyramid"]
    return SearchResult(
        query=d["query"],
        note_pyramid=NotePyramid(top=np["top"], middle=np["middle"], base=np["base"]),
        explanation=d["explanation"],
        perfumes=[
            PerfumeWithRelevance(perfume=perfume_from_dict(p["perfume"]), relevance=p["relevance"])
            for p in d["perfumes"]
        ],
        filters_applied=d.get("filters_applied"),
        total_found=d["total_found"],
    )


def _similar_to_dict(results: list[PerfumeWithRelevance]) -> list:
    return [{"perfume": perfume_to_dict(p.perfume), "relevance": p.relevance} for p in results]


def _similar_from_dict(data: list) -> list[PerfumeWithRelevance]:
    return [
        PerfumeWithRelevance(perfume=perfume_from_dict(p["perfume"]), relevance=p["relevance"])
        for p in data
    ]


def _filters_hash(filters: Optional[dict]) -> str:
    return hashlib.md5(json.dumps(filters or {}, sort_keys=True).encode()).hexdigest()[:8]


class SemanticSearchUseCase:

    def __init__(
        self,
        perfume_repository: IPerfumeRepository,
        embedding_service: IEmbeddingService,
        llm_service: ILLMService,
        cache: Optional[ICacheService] = None,
    ):
        self._perfume_repo = perfume_repository
        self._embedding_service = embedding_service
        self._llm_service = llm_service
        self._cache = cache

    def execute(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 5,
    ) -> SearchResult:
        query = normalize_query(query)
        filter_dict = filters.to_dict() if filters else None

        cache_key = f"search:{query}:{limit}:{_filters_hash(filter_dict)}"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                return _search_result_from_dict(cached)

        query_embedding = self._embedding_service.generate_embedding(query)
        results = self._perfume_repo.search_by_embedding(
            embedding=query_embedding,
            limit=limit,
            filters=filter_dict,
        )

        perfumes_with_relevance = [
            PerfumeWithRelevance(perfume=perfume, relevance=score)
            for perfume, score in results
        ]

        perfume_dicts = []
        for p in perfumes_with_relevance:
            pyramid = p.perfume.get_note_pyramid()
            all_notes = pyramid.top + pyramid.middle + pyramid.base
            tag_names = [t.tag for t in p.perfume.tags] if p.perfume.tags else []
            perfume_dicts.append({
                "name": p.perfume.name,
                "brand": p.perfume.brand,
                "family": p.perfume.family,
                "gender": p.perfume.gender,
                "notes": all_notes,
                "top_notes": pyramid.top,
                "middle_notes": pyramid.middle,
                "base_notes": pyramid.base,
                "tags": tag_names,
            })

        explanation, note_pyramid = self._llm_service.generate_search_result(
            query=query,
            perfumes=perfume_dicts,
        )

        result = SearchResult(
            query=query,
            note_pyramid=note_pyramid,
            explanation=explanation,
            perfumes=perfumes_with_relevance,
            filters_applied=filter_dict,
            total_found=len(perfumes_with_relevance),
        )

        if self._cache:
            self._cache.set(cache_key, _search_result_to_dict(result), _CACHE_TTL)

        return result


class FindSimilarUseCase:
    """
    Найти ароматы, похожие на заданный по embedding-вектору.

    Поиск ведётся по cosine-similarity в pgvector. Результат не зависит
    от пользователя, поэтому кэш — общий (без user_id в ключе).
    """

    def __init__(
        self,
        perfume_repository: IPerfumeRepository,
        cache: Optional[ICacheService] = None,
    ):
        self._perfume_repo = perfume_repository
        self._cache = cache

    def execute(self, perfume_id: int, limit: int = 5) -> list[PerfumeWithRelevance]:
        # Существование проверяется до кэша: иначе при обращении к
        # удалённому/несуществующему аромату клиент получил бы устаревший
        # ответ из кэша вместо корректного 404 на API-слое.
        if self._perfume_repo.get_by_id(perfume_id) is None:
            raise PerfumeNotFoundError(f"Perfume with id={perfume_id} not found")

        cache_key = f"similar:{perfume_id}:{limit}"
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return _similar_from_dict(cached)

        results = self._perfume_repo.find_similar(perfume_id=perfume_id, limit=limit)
        perfumes = [
            PerfumeWithRelevance(perfume=perfume, relevance=score)
            for perfume, score in results
        ]

        if self._cache is not None:
            self._cache.set(cache_key, _similar_to_dict(perfumes), _CACHE_TTL)

        return perfumes
