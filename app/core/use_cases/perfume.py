import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.core.entities import Perfume
from app.core.entities.perfume import Note, PerfumeNote
from app.core.value_objects.perfume import PerfumeTag
from app.core.exceptions import PerfumeNotFoundError
from app.core.interfaces import IPerfumeRepository, ICacheService

_CACHE_TTL = 180 * 24 * 3600  # 180 дней


@dataclass
class FiltersData:
    genders: list[str]
    families: list[str]
    product_types: list[str]
    categories: list[str] = field(default_factory=list)


def perfume_to_dict(p: Perfume) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "brand": p.brand,
        "year": p.year,
        "product_type": p.product_type,
        "family": p.family,
        "gender": p.gender,
        "category": p.category,
        "description": p.description,
        "review_summary": p.review_summary,
        "image_url": p.image_url,
        "source_url": p.source_url,
        "notes": [
            {"note": {"id": pn.note.id, "name": pn.note.name, "category": pn.note.category}, "level": pn.level}
            for pn in p.notes
        ],
        "tags": [{"tag": t.tag, "confidence": t.confidence, "source": t.source} for t in p.tags],
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def perfume_from_dict(d: dict) -> Perfume:
    notes = [PerfumeNote(note=Note(**n["note"]), level=n["level"]) for n in d.get("notes", [])]
    tags = [PerfumeTag(**t) for t in d.get("tags", [])]
    return Perfume(
        id=d["id"],
        name=d["name"],
        brand=d["brand"],
        year=d.get("year"),
        product_type=d.get("product_type"),
        family=d.get("family"),
        gender=d.get("gender"),
        category=d.get("category"),
        description=d.get("description"),
        review_summary=d.get("review_summary"),
        image_url=d.get("image_url"),
        source_url=d.get("source_url"),
        notes=notes,
        tags=tags,
        created_at=datetime.fromisoformat(d["created_at"]) if d.get("created_at") else None,
        updated_at=datetime.fromisoformat(d["updated_at"]) if d.get("updated_at") else None,
    )


class GetPerfumeUseCase:

    def __init__(self, perfume_repository: IPerfumeRepository, cache: Optional[ICacheService] = None):
        self._perfume_repo = perfume_repository
        self._cache = cache

    def execute(self, perfume_id: int) -> Perfume:
        key = f"perfume:{perfume_id}"
        if self._cache:
            cached = self._cache.get(key)
            if cached:
                return perfume_from_dict(cached)

        perfume = self._perfume_repo.get_by_id(perfume_id)
        if not perfume:
            raise PerfumeNotFoundError(f"Perfume with id={perfume_id} not found")

        if self._cache:
            self._cache.set(key, perfume_to_dict(perfume), _CACHE_TTL)
        return perfume


class GetFiltersUseCase:

    def __init__(self, perfume_repository: IPerfumeRepository, cache: Optional[ICacheService] = None):
        self._perfume_repo = perfume_repository
        self._cache = cache

    def execute(self) -> FiltersData:
        # v7: все ароматы получили категорию, удалены атомайзеры Travalo
        key = "filters:v7"
        if self._cache:
            cached = self._cache.get(key)
            if cached:
                return FiltersData(**cached)

        result = FiltersData(
            genders=self._perfume_repo.get_unique_genders(),
            families=self._perfume_repo.get_unique_families(),
            product_types=self._perfume_repo.get_unique_product_types(),
            categories=self._perfume_repo.get_unique_categories(),
        )
        if self._cache:
            self._cache.set(key, dataclasses.asdict(result), _CACHE_TTL)
        return result


class SuggestBrandsUseCase:

    def __init__(self, perfume_repository: IPerfumeRepository, cache: Optional[ICacheService] = None):
        self._perfume_repo = perfume_repository
        self._cache = cache

    def execute(self, q: str = "", limit: int = 20) -> list[str]:
        if not q:
            key = f"suggest:brands:top:{limit}"
            if self._cache:
                cached = self._cache.get(key)
                if cached is not None:
                    return cached
            result = self._perfume_repo.suggest_brands(q="", limit=limit)
            if self._cache:
                self._cache.set(key, result, _CACHE_TTL)
            return result

        return self._perfume_repo.suggest_brands(q=q, limit=limit)


class SuggestNotesUseCase:

    def __init__(self, perfume_repository: IPerfumeRepository, cache: Optional[ICacheService] = None):
        self._perfume_repo = perfume_repository
        self._cache = cache

    def execute(self, q: str = "", limit: int = 20) -> list[str]:
        if not q:
            key = f"suggest:notes:top:{limit}"
            if self._cache:
                cached = self._cache.get(key)
                if cached is not None:
                    return cached
            result = self._perfume_repo.suggest_notes(q="", limit=limit)
            if self._cache:
                self._cache.set(key, result, _CACHE_TTL)
            return result

        return self._perfume_repo.suggest_notes(q=q, limit=limit)
