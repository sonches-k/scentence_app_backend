"""
Value Objects для ароматов.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class NotePyramid:
    """
    Пирамида нот аромата.

    Immutable value object - определяется только содержимым.
    """
    top: tuple[str, ...] = field(default_factory=tuple)
    middle: tuple[str, ...] = field(default_factory=tuple)
    base: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        # Конвертируем списки в tuple для immutability
        object.__setattr__(self, 'top', tuple(self.top))
        object.__setattr__(self, 'middle', tuple(self.middle))
        object.__setattr__(self, 'base', tuple(self.base))

    def to_lists(self) -> dict[str, list[str]]:
        """Конвертировать в словарь со списками (для API)."""
        return {
            "top": list(self.top),
            "middle": list(self.middle),
            "base": list(self.base),
        }


@dataclass(frozen=True)
class PerfumeTag:
    """
    Тег аромата, извлеченный через RAG.

    Immutable value object.
    """
    tag: str
    confidence: Optional[float] = None
    source: Optional[str] = None
