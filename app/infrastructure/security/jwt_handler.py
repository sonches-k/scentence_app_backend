"""
Работа с JWT токенами.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.interfaces import IJWTService
from app.infrastructure.config import settings


def create_access_token(user_id: int) -> str:
    """Создать JWT токен для пользователя (вспомогательная функция)."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> int:
    """Декодировать JWT токен и вернуть user_id.

    Raises ValueError если токен невалиден или истёк.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise ValueError("Токен не содержит user_id")
        return int(sub)
    except JWTError as e:
        raise ValueError(f"Невалидный токен: {e}")


class JWTService(IJWTService):
    """Реализация IJWTService на базе python-jose."""

    def create_token(self, user_id: int) -> str:
        return create_access_token(user_id)

    def decode_token(self, token: str) -> int:
        return decode_access_token(token)
