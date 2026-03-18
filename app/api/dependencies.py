"""
Dependency Injection контейнер.

Создаёт и инжектирует зависимости в API роуты.
"""

import logging
from functools import lru_cache
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.infrastructure.config import settings
from app.infrastructure.database import get_db, SQLAlchemyPerfumeRepository, SQLAlchemyUserRepository
from app.infrastructure.external import OpenAIEmbeddingService, OpenAILLMService, DeepSeekLLMService
from app.infrastructure.external.embedding_service import SentenceTransformerEmbeddingService
from app.core.entities import User
from app.core.interfaces import (
    IPerfumeRepository,
    IUserRepository,
    IEmbeddingService,
    ILLMService,
    IEmailService,
    IJWTService,
)
from app.core.use_cases import (
    SemanticSearchUseCase,
    FindSimilarUseCase,
    GetPerfumeUseCase,
    GetFiltersUseCase,
    GetBrandsUseCase,
    GetFavoritesUseCase,
    AddFavoriteUseCase,
    RemoveFavoriteUseCase,
    GetSearchHistoryUseCase,
    RegisterUseCase,
    LoginUseCase,
    VerifyCodeUseCase,
)



def get_perfume_repository(
    db: Session = Depends(get_db),
) -> IPerfumeRepository:
    """Получить репозиторий ароматов."""
    return SQLAlchemyPerfumeRepository(db)


def get_user_repository(
    db: Session = Depends(get_db),
) -> IUserRepository:
    """Получить репозиторий пользователей."""
    return SQLAlchemyUserRepository(db)



def _is_valid_openai_key(key: str | None) -> bool:
    """Проверить, является ли ключ валидным OpenAI API ключом."""
    if not key:
        return False
    if key.startswith("sk-your") or key == "sk-your-api-key-here":
        return False
    return key.startswith("sk-") and len(key) > 20


@lru_cache()
def get_embedding_service() -> IEmbeddingService:
    """Получить сервис эмбеддингов (singleton)."""
    if _is_valid_openai_key(settings.OPENAI_API_KEY):
        return OpenAIEmbeddingService()
    return SentenceTransformerEmbeddingService("cointegrated/rubert-tiny2")


def _is_valid_deepseek_key(key: str | None) -> bool:
    """Проверить, является ли ключ валидным DeepSeek API ключом."""
    if not key:
        return False
    return key.startswith("sk-") and len(key) > 20


@lru_cache()
def get_llm_service() -> ILLMService:
    """Получить LLM сервис (singleton). Приоритет: OpenAI > DeepSeek."""
    if _is_valid_openai_key(settings.OPENAI_API_KEY):
        logger.info("LLM: используется OpenAILLMService")
        return OpenAILLMService()
    if _is_valid_deepseek_key(settings.DEEPSEEK_API_KEY):
        logger.info("LLM: используется DeepSeekLLMService")
        return DeepSeekLLMService()
    raise RuntimeError(
        "LLM-сервис не сконфигурирован: задайте DEEPSEEK_API_KEY или OPENAI_API_KEY в .env"
    )



def get_email_service() -> IEmailService:
    """Получить сервис отправки email."""
    from app.infrastructure.services.email_service import EmailService
    return EmailService()


def get_jwt_service() -> IJWTService:
    """Получить JWT сервис (singleton)."""
    from app.infrastructure.security.jwt_handler import JWTService
    return JWTService()



_http_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_http_bearer),
    user_repo: IUserRepository = Depends(get_user_repository),
) -> User:
    """Dependency: возвращает текущего пользователя из Bearer токена. 401 если нет токена."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Необходима авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        from app.infrastructure.security.jwt_handler import decode_access_token
        user_id = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или истёкший токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )
    return user


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_http_bearer),
    user_repo: IUserRepository = Depends(get_user_repository),
) -> Optional[User]:
    """Dependency: возвращает пользователя если токен передан, иначе None."""
    if not credentials:
        return None
    try:
        from app.infrastructure.security.jwt_handler import decode_access_token
        user_id = decode_access_token(credentials.credentials)
        return user_repo.get_by_id(user_id)
    except Exception:
        return None



def get_semantic_search_use_case(
    perfume_repo: IPerfumeRepository = Depends(get_perfume_repository),
    embedding_service: IEmbeddingService = Depends(get_embedding_service),
    llm_service: ILLMService = Depends(get_llm_service),
) -> SemanticSearchUseCase:
    """Получить use case семантического поиска."""
    return SemanticSearchUseCase(
        perfume_repository=perfume_repo,
        embedding_service=embedding_service,
        llm_service=llm_service,
    )


def get_find_similar_use_case(
    perfume_repo: IPerfumeRepository = Depends(get_perfume_repository),
) -> FindSimilarUseCase:
    """Получить use case поиска похожих."""
    return FindSimilarUseCase(perfume_repository=perfume_repo)


def get_perfume_use_case(
    perfume_repo: IPerfumeRepository = Depends(get_perfume_repository),
) -> GetPerfumeUseCase:
    """Получить use case получения аромата."""
    return GetPerfumeUseCase(perfume_repository=perfume_repo)


def get_filters_use_case(
    perfume_repo: IPerfumeRepository = Depends(get_perfume_repository),
) -> GetFiltersUseCase:
    """Получить use case получения фильтров."""
    return GetFiltersUseCase(perfume_repository=perfume_repo)


def get_brands_use_case(
    perfume_repo: IPerfumeRepository = Depends(get_perfume_repository),
) -> GetBrandsUseCase:
    """Получить use case получения брендов."""
    return GetBrandsUseCase(perfume_repository=perfume_repo)


def get_favorites_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
) -> GetFavoritesUseCase:
    """Получить use case получения избранного."""
    return GetFavoritesUseCase(user_repository=user_repo)


def get_add_favorite_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
    perfume_repo: IPerfumeRepository = Depends(get_perfume_repository),
) -> AddFavoriteUseCase:
    """Получить use case добавления в избранное."""
    return AddFavoriteUseCase(
        user_repository=user_repo,
        perfume_repository=perfume_repo,
    )


def get_remove_favorite_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
) -> RemoveFavoriteUseCase:
    """Получить use case удаления из избранного."""
    return RemoveFavoriteUseCase(user_repository=user_repo)


def get_search_history_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
) -> GetSearchHistoryUseCase:
    """Получить use case получения истории."""
    return GetSearchHistoryUseCase(user_repository=user_repo)



def get_register_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
    email_service: IEmailService = Depends(get_email_service),
) -> RegisterUseCase:
    """Получить use case регистрации."""
    return RegisterUseCase(user_repo=user_repo, email_service=email_service)


def get_login_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
    email_service: IEmailService = Depends(get_email_service),
) -> LoginUseCase:
    """Получить use case входа."""
    return LoginUseCase(user_repo=user_repo, email_service=email_service)


def get_verify_code_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
    jwt_service: IJWTService = Depends(get_jwt_service),
) -> VerifyCodeUseCase:
    """Получить use case верификации кода."""
    return VerifyCodeUseCase(user_repo=user_repo, jwt_service=jwt_service)
