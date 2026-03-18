"""
Value Objects - объекты-значения.

Неизменяемые объекты без идентичности, определяемые только своими атрибутами.
"""

from app.core.value_objects.perfume import NotePyramid, PerfumeTag
from app.core.value_objects.search import SearchFilters

__all__ = [
    "NotePyramid",
    "PerfumeTag",
    "SearchFilters",
]
