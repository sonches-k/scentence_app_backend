"""
Pydantic схемы для API - модели ароматов.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class NoteBase(BaseModel):
    """Базовая схема ноты."""
    name: str
    category: Optional[str] = None


class Note(NoteBase):
    """Схема ноты с ID."""
    id: int
    
    class Config:
        from_attributes = True


class PerfumeNoteResponse(BaseModel):
    """Схема ноты в составе аромата."""
    note: Note
    level: str  # Top, Middle, Base
    
    class Config:
        from_attributes = True


class NotePyramid(BaseModel):
    """
    Пирамида нот аромата.

    Классическая трёхуровневая структура парфюмерной композиции:
    верхние ноты раскрываются первыми (5–15 мин), сердце — основа аромата,
    база — шлейф, остающийся через несколько часов.
    """

    top: List[str] = Field(
        default_factory=list,
        description="Верхние ноты (head notes) — первое впечатление",
        examples=[["Бергамот", "Лимон", "Грейпфрут"]],
    )
    middle: List[str] = Field(
        default_factory=list,
        description="Ноты сердца (heart notes) — основа букета",
        examples=[["Жасмин", "Роза", "Герань"]],
    )
    base: List[str] = Field(
        default_factory=list,
        description="Базовые ноты (base notes) — шлейф и стойкость",
        examples=[["Мускус", "Сандал", "Ваниль"]],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "top": ["Бергамот", "Лимон"],
                    "middle": ["Жасмин", "Роза"],
                    "base": ["Мускус", "Ваниль", "Сандал"],
                }
            ]
        }
    }


class PerfumeTagResponse(BaseModel):
    """Схема тега аромата."""
    tag: str
    confidence: Optional[float] = None
    source: Optional[str] = None
    
    class Config:
        from_attributes = True


class PerfumeBase(BaseModel):
    """Базовая схема аромата."""
    name: str = Field(..., min_length=1, max_length=255)
    brand: str = Field(..., min_length=1, max_length=255)
    year: Optional[int] = Field(None, ge=1800, le=2030)
    product_type: Optional[str] = Field(None, max_length=50)
    family: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=512)
    source_url: Optional[str] = Field(None, max_length=512)


class PerfumeCreate(PerfumeBase):
    """Схема для создания аромата."""
    pass


class PerfumeUpdate(BaseModel):
    """Схема для обновления аромата."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    brand: Optional[str] = Field(None, min_length=1, max_length=255)
    year: Optional[int] = Field(None, ge=1800, le=2030)
    product_type: Optional[str] = Field(None, max_length=50)
    family: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=512)


class PerfumeResponse(PerfumeBase):
    """Схема ответа с информацией об аромате."""
    id: int
    notes: List[PerfumeNoteResponse] = Field(default_factory=list)
    tags: List[PerfumeTagResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class PerfumeCard(BaseModel):
    """Схема карточки аромата для списка (упрощенная)."""
    id: int
    name: str
    brand: str
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    family: Optional[str] = None
    gender: Optional[str] = None
    top_notes: List[str] = Field(default_factory=list, description="Верхние ноты (до 5)")
    middle_notes: List[str] = Field(default_factory=list, description="Средние ноты (до 5)")
    base_notes: List[str] = Field(default_factory=list, description="Базовые ноты (до 5)")
    
    class Config:
        from_attributes = True


class PerfumeWithRelevance(PerfumeCard):
    """
    Карточка аромата с оценкой релевантности поиска.

    `relevance` вычисляется как `1 - cosine_distance` между эмбеддингом
    запроса и эмбеддингом аромата. Значение 1.0 — идеальное совпадение.
    """

    relevance: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Оценка релевантности запросу: 0.0 — нет совпадения, 1.0 — максимальное",
        examples=[0.87],
    )


class FiltersResponse(BaseModel):
    """Доступные значения фильтров."""
    genders: List[str]
    families: List[str]
    product_types: List[str]
    brands: List[str]
    notes: List[str]
