"""
Use Cases для поиска ароматов.
"""

from dataclasses import dataclass
from typing import Optional

from app.core.entities import NotePyramid, PerfumeWithRelevance
from app.core.value_objects import SearchFilters
from app.core.interfaces import (
    IPerfumeRepository,
    IEmbeddingService,
    ILLMService,
)


@dataclass
class SearchResult:
    """Результат поиска."""
    query: str
    note_pyramid: NotePyramid
    explanation: str
    perfumes: list[PerfumeWithRelevance]
    filters_applied: Optional[dict]
    total_found: int


class SemanticSearchUseCase:
    """
    Use Case: Семантический поиск ароматов.

    Принимает текстовое описание и возвращает релевантные ароматы
    с пояснением от LLM.
    """

    def __init__(
        self,
        perfume_repository: IPerfumeRepository,
        embedding_service: IEmbeddingService,
        llm_service: ILLMService,
    ):
        self._perfume_repo = perfume_repository
        self._embedding_service = embedding_service
        self._llm_service = llm_service

    def execute(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 5,
    ) -> SearchResult:
        """Выполнить семантический поиск."""
        query_embedding = self._embedding_service.generate_embedding(query)

        filter_dict = filters.to_dict() if filters else None
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
        explanation = self._llm_service.generate_search_explanation(
            query=query,
            perfumes=perfume_dicts,
        )

        note_pyramid = self._llm_service.extract_note_pyramid(query)

        return SearchResult(
            query=query,
            note_pyramid=note_pyramid,
            explanation=explanation,
            perfumes=perfumes_with_relevance,
            filters_applied=filter_dict,
            total_found=len(perfumes_with_relevance),
        )


class FindSimilarUseCase:
    """
    Use Case: Поиск похожих ароматов.

    Находит ароматы, похожие на указанный, на основе
    векторного сходства.
    """

    def __init__(self, perfume_repository: IPerfumeRepository):
        self._perfume_repo = perfume_repository

    def execute(
        self,
        perfume_id: int,
        limit: int = 5,
    ) -> list[PerfumeWithRelevance]:
        """Найти похожие ароматы."""
        results = self._perfume_repo.find_similar(
            perfume_id=perfume_id,
            limit=limit,
        )

        return [
            PerfumeWithRelevance(perfume=perfume, relevance=score)
            for perfume, score in results
        ]
