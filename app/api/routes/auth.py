"""
POST /register — код на email (аккаунт создаётся при верификации)
POST /login    — код на email (только если пользователь уже есть)
POST /verify   — проверить код → access + refresh токены
POST /refresh  — новый access по refresh
POST /logout   — инвалидировать refresh в БД
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas.auth import (
    RegisterRequest,
    VerifyRequest,
    TokenResponse,
    MessageResponse,
    RefreshRequest,
)
from app.api.dependencies import (
    get_register_use_case,
    get_login_use_case,
    get_verify_code_use_case,
    get_refresh_token_use_case,
    get_logout_use_case,
)
from app.core.exceptions import (
    InvalidCodeError,
    InvalidRefreshTokenError,
    TooManyAttemptsError,
    UserNotFoundError,
)
from app.core.use_cases.auth import (
    RegisterUseCase,
    LoginUseCase,
    VerifyCodeUseCase,
    RefreshTokenUseCase,
    LogoutUseCase,
)

router = APIRouter()


@router.post("/register", response_model=MessageResponse, summary="Регистрация / запрос кода")
async def register(
    request: RegisterRequest,
    use_case: RegisterUseCase = Depends(get_register_use_case),
):
    """Если пользователь уже существует — код обновляется."""
    use_case.execute(str(request.email))
    return MessageResponse(message="Код отправлен на email")


@router.post("/login", response_model=MessageResponse, summary="Вход")
async def login(
    request: RegisterRequest,
    use_case: LoginUseCase = Depends(get_login_use_case),
):
    """404 если email не зарегистрирован."""
    try:
        use_case.execute(str(request.email))
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден. Сначала зарегистрируйтесь через /register.",
        )
    return MessageResponse(message="Код отправлен на email")


@router.post("/verify", response_model=TokenResponse, summary="Верификация кода")
async def verify(
    request: VerifyRequest,
    use_case: VerifyCodeUseCase = Depends(get_verify_code_use_case),
):
    """
    401 — неверный или истёкший код
    429 — превышен лимит попыток (5)
    """
    try:
        tokens = use_case.execute(str(request.email), request.code)
    except TooManyAttemptsError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except InvalidCodeError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/refresh", response_model=TokenResponse, summary="Обновление access-токена")
async def refresh(
    request: RefreshRequest,
    use_case: RefreshTokenUseCase = Depends(get_refresh_token_use_case),
):
    """401 — токен не найден или истёк."""
    try:
        new_access = use_case.execute(request.refresh_token)
    except InvalidRefreshTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return TokenResponse(access_token=new_access, refresh_token=request.refresh_token)


@router.post("/logout", response_model=MessageResponse, summary="Выход")
async def logout(
    request: RefreshRequest,
    use_case: LogoutUseCase = Depends(get_logout_use_case),
):
    use_case.execute(request.refresh_token)
    return MessageResponse(message="Вы вышли из аккаунта")
