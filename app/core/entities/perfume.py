"""
Доменные сущности для ароматов.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.core.value_objects import NotePyramid, PerfumeTag


@dataclass
class Note:
    """Парфюмерная нота."""
    id: int
    name: str
    category: Optional[str] = None

    def __repr__(self) -> str:
        return f"Note(id={self.id}, name={self.name!r})"


@dataclass
class PerfumeNote:
    """Связь аромата с нотой."""
    note: Note
    level: str  # Top, Middle, Base


@dataclass
class Perfume:
    """Аромат - основная доменная сущность."""
    id: int
    name: str
    brand: str
    year: Optional[int] = None
    product_type: Optional[str] = None
    family: Optional[str] = None
    gender: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    notes: list[PerfumeNote] = field(default_factory=list)
    tags: list[PerfumeTag] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __repr__(self) -> str:
        return f"Perfume(id={self.id}, name={self.name!r}, brand={self.brand!r})"

    def get_note_pyramid(self) -> NotePyramid:
        """Получить пирамиду нот аромата."""
        top = []
        middle = []
        base = []
        for pn in self.notes:
            note_name = pn.note.name
            if pn.level.lower() == "top":
                top.append(note_name)
            elif pn.level.lower() == "middle":
                middle.append(note_name)
            elif pn.level.lower() == "base":
                base.append(note_name)
        return NotePyramid(top=top, middle=middle, base=base)


@dataclass
class PerfumeWithRelevance:
    """Аромат с оценкой релевантности для результатов поиска."""
    perfume: Perfume
    relevance: float  # 0.0 - 1.0

    def __repr__(self) -> str:
        return f"PerfumeWithRelevance(perfume={self.perfume!r}, relevance={self.relevance:.2f})"
