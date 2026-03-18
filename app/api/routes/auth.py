"""
API эндпоинты аутентификации.

POST /register — отправить код (создаёт аккаунт при верификации)
POST /login    — отправить код (только для существующих)
POST /verify   — проверить код, получить JWT
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas.auth import (
    RegisterRequest,
    VerifyRequest,
    TokenResponse,
    MessageResponse,
)
from app.api.dependencies import (
    get_register_use_case,
    get_login_use_case,
    get_verify_code_use_case,
)
from app.core.exceptions import InvalidCodeError, TooManyAttemptsError, UserNotFoundError
from app.core.use_cases.auth import (
    RegisterUseCase,
    LoginUseCase,
    VerifyCodeUseCase,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=MessageResponse,
    summary="Регистрация / запрос кода",
)
async def register(
    request: RegisterRequest,
    use_case: RegisterUseCase = Depends(get_register_use_case),
):
    """
    Генерирует 6-значный код и отправляет на email.
    Если пользователь уже существует — код обновляется.
    Аккаунт создаётся при успешной верификации.
    """
    use_case.execute(str(request.email))
    return MessageResponse(message="Код отправлен на email")


@router.post(
    "/login",
    response_model=MessageResponse,
    summary="Вход для существующих пользователей",
)
async def login(
    request: RegisterRequest,
    use_case: LoginUseCase = Depends(get_login_use_case),
):
    """
    Отправляет код только если пользователь уже зарегистрирован.
    Возвращает 404 если email не найден.
    """
    try:
        use_case.execute(str(request.email))
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден. Сначала зарегистрируйтесь через /register.",
        )
    return MessageResponse(message="Код отправлен на email")


@router.post(
    "/verify",
    response_model=TokenResponse,
    summary="Верификация кода",
)
async def verify(
    request: VerifyRequest,
    use_case: VerifyCodeUseCase = Depends(get_verify_code_use_case),
):
    """
    Проверяет 6-значный код. При успехе возвращает JWT (Bearer токен, 7 дней).
    - 401 — неверный или истёкший код
    - 429 — превышен лимит попыток (5)
    """
    try:
        token = use_case.execute(str(request.email), request.code)
    except TooManyAttemptsError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )
    except InvalidCodeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    return TokenResponse(access_token=token)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Выход из аккаунта",
)
async def logout():
    """
    Выход из аккаунта.

    JWT — stateless токены, поэтому реальная инвалидация происходит на клиенте
    (удаление токена из хранилища). Эндпоинт существует для совместимости с ТЗ.
    """
    return MessageResponse(message="Вы вышли из аккаунта")
