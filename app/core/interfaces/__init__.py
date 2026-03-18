"""
Interfaces - абстрактные интерфейсы (порты).

Определяют контракты для взаимодействия с внешним миром.
Реализации находятся в infrastructure/.
"""

from app.core.interfaces.repositories import (
    IPerfumeRepository,
    IUserRepository,
)
from app.core.interfaces.services import (
    IEmbeddingService,
    ILLMService,
    IEmailService,
    IJWTService,
)

__all__ = [
    "IPerfumeRepository",
    "IUserRepository",
    "IEmbeddingService",
    "ILLMService",
    "IEmailService",
    "IJWTService",
]
