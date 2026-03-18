"""
Value Objects для поиска.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SearchFilters:
    """
    Фильтры для поиска ароматов.

    Immutable value object.
    """
    genders: Optional[tuple[str, ...]] = None
    families: Optional[tuple[str, ...]] = None
    product_types: Optional[tuple[str, ...]] = None
    brands: Optional[tuple[str, ...]] = None
    notes: Optional[tuple[str, ...]] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None

    def to_dict(self) -> dict:
        """Конвертировать в словарь, исключая None значения."""
        result = {}
        if self.genders:
            result["genders"] = list(self.genders)
        if self.families:
            result["families"] = list(self.families)
        if self.product_types:
            result["product_types"] = list(self.product_types)
        if self.brands:
            result["brands"] = list(self.brands)
        if self.notes:
            result["notes"] = list(self.notes)
        if self.year_from is not None:
            result["year_from"] = self.year_from
        if self.year_to is not None:
            result["year_to"] = self.year_to
        return result

    @classmethod
    def from_lists(
        cls,
        genders: Optional[list[str]] = None,
        families: Optional[list[str]] = None,
        product_types: Optional[list[str]] = None,
        brands: Optional[list[str]] = None,
        notes: Optional[list[str]] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
    ) -> "SearchFilters":
        """Создать из списков (для удобства API)."""
        return cls(
            genders=tuple(genders) if genders else None,
            families=tuple(families) if families else None,
            product_types=tuple(product_types) if product_types else None,
            brands=tuple(brands) if brands else None,
            notes=tuple(notes) if notes else None,
            year_from=year_from,
            year_to=year_to,
        )
