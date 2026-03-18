"""
Use Cases для работы с ароматами.
"""

from dataclasses import dataclass
from typing import Optional

from app.core.entities import Perfume
from app.core.exceptions import PerfumeNotFoundError
from app.core.interfaces import IPerfumeRepository


@dataclass
class FiltersData:
    """Доступные значения фильтров."""
    genders: list[str]
    families: list[str]
    product_types: list[str]
    brands: list[str]
    notes: list[str]


class GetPerfumeUseCase:
    """
    Use Case: Получение информации об аромате.
    """

    def __init__(self, perfume_repository: IPerfumeRepository):
        self._perfume_repo = perfume_repository

    def execute(self, perfume_id: int) -> Perfume:
        """Получить аромат по ID."""
        perfume = self._perfume_repo.get_by_id(perfume_id)
        if not perfume:
            raise PerfumeNotFoundError(f"Perfume with id={perfume_id} not found")
        return perfume


class GetFiltersUseCase:
    """
    Use Case: Получение доступных значений фильтров.
    """

    def __init__(self, perfume_repository: IPerfumeRepository):
        self._perfume_repo = perfume_repository

    def execute(self) -> FiltersData:
        """Получить все уникальные значения для фильтров."""
        return FiltersData(
            genders=self._perfume_repo.get_unique_genders(),
            families=self._perfume_repo.get_unique_families(),
            product_types=self._perfume_repo.get_unique_product_types(),
            brands=self._perfume_repo.get_unique_brands(),
            notes=self._perfume_repo.get_unique_notes(),
        )


class GetBrandsUseCase:
    """
    Use Case: Получение списка брендов.
    """

    def __init__(self, perfume_repository: IPerfumeRepository):
        self._perfume_repo = perfume_repository

    def execute(self) -> list[str]:
        """Получить список всех брендов."""
        return self._perfume_repo.get_unique_brands()
