import random
import string
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from app.core.entities import User
from app.core.exceptions import (
    InvalidCodeError,
    InvalidRefreshTokenError,
    TooManyAttemptsError,
    UserNotFoundError,
)
from app.core.interfaces import IUserRepository, IEmailService, IJWTService

CODE_TTL_MINUTES = 10
MAX_ATTEMPTS = 5


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str


def _generate_code() -> str:
    return "".join(random.choices(string.digits, k=6))


class RegisterUseCase:
    """Пользователь создаётся при успешной верификации, не здесь."""

    def __init__(self, user_repo: IUserRepository, email_service: IEmailService):
        self._user_repo = user_repo
        self._email_service = email_service

    def execute(self, email: str) -> None:
        code = _generate_code()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES)
        self._user_repo.delete_verification_codes(email)
        self._user_repo.create_verification_code(email, code, expires_at)
        self._email_service.send_verification_code(email, code)


class LoginUseCase:

    def __init__(self, user_repo: IUserRepository, email_service: IEmailService):
        self._user_repo = user_repo
        self._email_service = email_service

    def execute(self, email: str) -> None:
        user = self._user_repo.get_by_email(email)
        if not user:
            raise UserNotFoundError(email)
        code = _generate_code()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES)
        self._user_repo.delete_verification_codes(email)
        self._user_repo.create_verification_code(email, code, expires_at)
        self._email_service.send_verification_code(email, code)


class VerifyCodeUseCase:
    """Создаёт пользователя при первом входе, возвращает пару токенов."""

    def __init__(self, user_repo: IUserRepository, jwt_service: IJWTService):
        self._user_repo = user_repo
        self._jwt_service = jwt_service

    def execute(self, email: str, code: str) -> AuthTokens:
        verification = self._user_repo.get_latest_verification_code(email)
        if not verification:
            raise InvalidCodeError("Код не найден. Запросите новый.")

        if verification.attempts >= MAX_ATTEMPTS:
            raise TooManyAttemptsError("Превышен лимит попыток. Запросите новый код.")

        now = datetime.now(timezone.utc)
        expires_at = verification.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
            raise InvalidCodeError("Код истёк. Запросите новый.")

        if verification.code != code:
            self._user_repo.increment_code_attempts(verification.id)
            remaining = MAX_ATTEMPTS - verification.attempts - 1
            raise InvalidCodeError(f"Неверный код. Осталось попыток: {remaining}")

        self._user_repo.delete_verification_codes(email)
        user = self._user_repo.get_by_email(email)
        if not user:
            user = self._user_repo.create(email)

        access_token = self._jwt_service.create_token(user.id)
        refresh_token, refresh_expires = self._jwt_service.issue_refresh_credentials()
        self._user_repo.create_refresh_token(
            user_id=user.id,
            token=refresh_token,
            expires_at=refresh_expires,
        )
        return AuthTokens(access_token=access_token, refresh_token=refresh_token)


class RefreshTokenUseCase:

    def __init__(self, user_repo: IUserRepository, jwt_service: IJWTService):
        self._user_repo = user_repo
        self._jwt_service = jwt_service

    def execute(self, refresh_token: str) -> str:
        stored = self._user_repo.get_refresh_token(refresh_token)
        if not stored:
            raise InvalidRefreshTokenError("Refresh-токен не найден или уже использован.")

        expires_at = stored.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            self._user_repo.delete_refresh_token(refresh_token)
            raise InvalidRefreshTokenError("Refresh-токен истёк. Выполните вход заново.")

        return self._jwt_service.create_token(stored.user_id)


class LogoutUseCase:

    def __init__(self, user_repo: IUserRepository):
        self._user_repo = user_repo

    def execute(self, refresh_token: str) -> None:
        self._user_repo.delete_refresh_token(refresh_token)
