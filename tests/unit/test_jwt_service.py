import pytest
from jose import jwt

from app.infrastructure.config import settings
from app.infrastructure.security.jwt_handler import JWTService, decode_access_token


pytestmark = pytest.mark.unit


class TestJWTService:

    def test_create_and_decode_token(self):
        service = JWTService()
        token = service.create_token(user_id=42)
        user_id = service.decode_token(token)
        assert user_id == 42

    def test_decode_invalid_token_raises(self):
        service = JWTService()
        with pytest.raises(ValueError):
            service.decode_token("invalid.token.string")

    def test_decode_token_with_wrong_type_raises(self):
        payload = {"sub": "1", "type": "refresh"}
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)

        with pytest.raises(ValueError, match="Неверный тип токена"):
            decode_access_token(token)

    def test_decode_token_without_type_raises(self):
        payload = {"sub": "1"}
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)

        with pytest.raises(ValueError, match="Неверный тип токена"):
            decode_access_token(token)

    def test_decode_token_missing_sub_raises(self):
        payload = {"type": "access"}
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)

        with pytest.raises(ValueError):
            decode_access_token(token)

    def test_issue_refresh_credentials_returns_token_and_expiry(self):
        service = JWTService()
        token, expires_at = service.issue_refresh_credentials()

        assert isinstance(token, str)
        assert len(token) == 64
        from datetime import datetime
        assert isinstance(expires_at, datetime)
