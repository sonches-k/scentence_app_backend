"""
Модуль безопасности — JWT и аутентификация.
"""

from app.infrastructure.security.jwt_handler import create_access_token, decode_access_token

__all__ = ["create_access_token", "decode_access_token"]
