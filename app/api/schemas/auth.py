"""
Pydantic схемы для аутентификации.
"""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Запрос на регистрацию / запрос кода."""
    email: EmailStr = Field(..., description="Email пользователя")


class VerifyRequest(BaseModel):
    """Запрос на верификацию кода."""
    email: EmailStr = Field(..., description="Email пользователя")
    code: str = Field(..., min_length=6, max_length=6, description="6-значный код")


class TokenResponse(BaseModel):
    """Ответ с JWT токеном."""
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    """Простой ответ с сообщением."""
    message: str


class ProfileResponse(BaseModel):
    """Профиль пользователя."""
    id: int
    email: str
    name: str | None = None


class UpdateProfileRequest(BaseModel):
    """Запрос на обновление профиля."""
    name: str = Field(..., min_length=2, max_length=50, description="Имя пользователя")
