import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.interfaces import IJWTService
from app.infrastructure.config import settings


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> int:
    """Raises ValueError если токен невалиден или истёк."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise ValueError("Токен не содержит user_id")
        return int(sub)
    except JWTError as e:
        raise ValueError(f"Невалидный токен: {e}")


class JWTService(IJWTService):

    def create_token(self, user_id: int) -> str:
        return create_access_token(user_id)

    def decode_token(self, token: str) -> int:
        return decode_access_token(token)

    def issue_refresh_credentials(self) -> tuple[str, datetime]:
        token = secrets.token_hex(32)
        expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        return token, expires
