from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from app.api.schemas.perfume import PerfumeWithRelevance, NotePyramid
from app.infrastructure.config import settings


class SearchFilters(BaseModel):
    """
    Структурные фильтры для уточнения семантического поиска.

    Все поля опциональны и применяются совместно (AND-логика).
    Доступные значения для каждого поля возвращает `GET /perfumes/filters`.
    """

    genders: Optional[List[str]] = Field(
        None,
        description="Пол целевой аудитории: `Male`, `Female`, `Unisex`",
        examples=[["Female", "Unisex"]],
    )
    families: Optional[List[str]] = Field(
        None,
        description="Ольфакторное семейство: Floral, Oriental, Woody, Fresh и др.",
        examples=[["Oriental", "Woody"]],
    )
    product_types: Optional[List[str]] = Field(
        None,
        description="Тип продукта: `EDP` (Eau de Parfum), `EDT` (Eau de Toilette), `Parfum` и др.",
        examples=[["EDP", "Parfum"]],
    )
    categories: Optional[List[str]] = Field(
        None,
        description="Категория (сегмент) аромата: `Люкс`, `Нишевая`, `Восточная`, `Масляная`, `Винтажная` и др.",
        examples=[["Люкс", "Нишевая"]],
    )
    brands: Optional[List[str]] = Field(
        None,
        description="Бренды производителей",
        examples=[["Chanel", "Dior", "Tom Ford"]],
    )
    notes: Optional[List[str]] = Field(
        None,
        description="Парфюмерные ноты (любого уровня — верхние, сердце, база)",
        examples=[["ваниль", "сандал"]],
    )
    year_from: Optional[int] = Field(
        None,
        ge=1800,
        description="Год выпуска — от (включительно)",
        examples=[2010],
    )
    year_to: Optional[int] = Field(
        None,
        le=2030,
        description="Год выпуска — до (включительно)",
        examples=[2024],
    )

    @model_validator(mode="after")
    def check_year_range(self) -> "SearchFilters":
        if self.year_from is not None and self.year_to is not None and self.year_from > self.year_to:
            raise ValueError("year_from не может быть больше year_to")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "genders": ["Female", "Unisex"],
                    "families": ["Oriental", "Floral"],
                    "product_types": ["EDP"],
                    "year_from": 2010,
                }
            ]
        }
    }


class SearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=settings.MIN_SEARCH_QUERY_LENGTH,
        max_length=settings.MAX_SEARCH_QUERY_LENGTH,
        description="Свободное описание желаемого аромата (от 3 до 1000 символов)",
        examples=["тёплый уютный аромат для зимних вечеров"],
    )
    filters: Optional[SearchFilters] = Field(
        None,
        description="Структурные фильтры для сужения области поиска",
    )
    limit: int = Field(
        5,
        ge=1,
        le=20,
        description="Максимальное количество ароматов в ответе (1–20)",
        examples=[5],
    )

    @field_validator("query")
    @classmethod
    def normalize_query(cls, v: str) -> str:
        return " ".join(v.strip().split())

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "тёплый уютный аромат для зимних вечеров",
                    "limit": 5,
                },
                {
                    "query": "свежий и лёгкий на лето",
                    "limit": 5,
                    "filters": {"genders": ["Unisex"], "families": ["Fresh"]},
                },
                {
                    "query": "аромат для офиса, не навязчивый",
                    "limit": 5,
                    "filters": {"product_types": ["EDT"], "genders": ["Unisex"]},
                },
            ]
        }
    }


class SearchResponse(BaseModel):
    query: str = Field(..., description="Исходный запрос пользователя")
    note_pyramid: NotePyramid = Field(
        ...,
        description=(
            "Пирамида нот, которую LLM извлёк из текстового описания. "
            "Показывает, как система интерпретировала запрос."
        ),
    )
    explanation: str = Field(
        ...,
        description=(
            "Текстовое пояснение от LLM (до 500 символов): "
            "почему найденные ароматы соответствуют запросу."
        ),
    )
    perfumes: List[PerfumeWithRelevance] = Field(
        ...,
        description="Найденные ароматы, отсортированные по убыванию релевантности",
    )
    filters_applied: Optional[Dict[str, Any]] = Field(
        None,
        description="Применённые структурные фильтры (если были переданы)",
    )
    total_found: int = Field(
        ...,
        description="Количество ароматов в ответе (≤ limit)",
    )


class SimilarSearchResponse(BaseModel):
    source_perfume_id: int = Field(
        ...,
        description="ID аромата, для которого выполнялся поиск",
    )
    similar_perfumes: List[PerfumeWithRelevance] = Field(
        ...,
        description="Похожие ароматы, отсортированные по убыванию сходства",
    )
