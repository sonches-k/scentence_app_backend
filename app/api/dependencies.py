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
    ICacheService,
)
from app.core.use_cases import (
    SemanticSearchUseCase,
    FindSimilarUseCase,
    GetPerfumeUseCase,
    GetFiltersUseCase,
    SuggestBrandsUseCase,
    SuggestNotesUseCase,
    GetFavoritesUseCase,
    AddFavoriteUseCase,
    RemoveFavoriteUseCase,
    GetSearchHistoryUseCase,
    DeleteSearchHistoryEntryUseCase,
    ClearSearchHistoryUseCase,
    RegisterUseCase,
    LoginUseCase,
    VerifyCodeUseCase,
)
from app.core.use_cases.auth import RefreshTokenUseCase, LogoutUseCase


def get_perfume_repository(db: Session = Depends(get_db)) -> IPerfumeRepository:
    return SQLAlchemyPerfumeRepository(db)


def get_user_repository(db: Session = Depends(get_db)) -> IUserRepository:
    return SQLAlchemyUserRepository(db)


def _is_valid_openai_key(key: str | None) -> bool:
    if not key:
        return False
    if key.startswith("sk-your") or key == "sk-your-api-key-here":
        return False
    return key.startswith("sk-") and len(key) > 20


def _is_valid_deepseek_key(key: str | None) -> bool:
    if not key:
        return False
    return key.startswith("sk-") and len(key) > 20


@lru_cache()
def get_embedding_service() -> IEmbeddingService:
    if _is_valid_openai_key(settings.OPENAI_API_KEY):
        return OpenAIEmbeddingService()
    return SentenceTransformerEmbeddingService("intfloat/multilingual-e5-large")


@lru_cache()
def get_llm_service() -> ILLMService:
    """Приоритет: OpenAI → DeepSeek."""
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
    from app.infrastructure.services.email_service import EmailService
    return EmailService()


def get_jwt_service() -> IJWTService:
    from app.infrastructure.security.jwt_handler import JWTService
    return JWTService()


@lru_cache()
def get_cache_service() -> Optional[ICacheService]:
    if not settings.REDIS_URL:
        return None
    try:
        from app.infrastructure.cache.redis_service import RedisCacheService
        return RedisCacheService(settings.REDIS_URL)
    except Exception:
        return None


_http_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_http_bearer),
    user_repo: IUserRepository = Depends(get_user_repository),
) -> User:
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    return user


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_http_bearer),
    user_repo: IUserRepository = Depends(get_user_repository),
) -> Optional[User]:
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
    cache: Optional[ICacheService] = Depends(get_cache_service),
) -> SemanticSearchUseCase:
    return SemanticSearchUseCase(
        perfume_repository=perfume_repo,
        embedding_service=embedding_service,
        llm_service=llm_service,
        cache=cache,
    )


def get_find_similar_use_case(
    perfume_repo: IPerfumeRepository = Depends(get_perfume_repository),
    cache: Optional[ICacheService] = Depends(get_cache_service),
) -> FindSimilarUseCase:
    return FindSimilarUseCase(perfume_repository=perfume_repo, cache=cache)


def get_perfume_use_case(
    perfume_repo: IPerfumeRepository = Depends(get_perfume_repository),
    cache: Optional[ICacheService] = Depends(get_cache_service),
) -> GetPerfumeUseCase:
    return GetPerfumeUseCase(perfume_repository=perfume_repo, cache=cache)


def get_filters_use_case(
    perfume_repo: IPerfumeRepository = Depends(get_perfume_repository),
    cache: Optional[ICacheService] = Depends(get_cache_service),
) -> GetFiltersUseCase:
    return GetFiltersUseCase(perfume_repository=perfume_repo, cache=cache)


def get_suggest_brands_use_case(
    perfume_repo: IPerfumeRepository = Depends(get_perfume_repository),
    cache: Optional[ICacheService] = Depends(get_cache_service),
) -> SuggestBrandsUseCase:
    return SuggestBrandsUseCase(perfume_repository=perfume_repo, cache=cache)


def get_suggest_notes_use_case(
    perfume_repo: IPerfumeRepository = Depends(get_perfume_repository),
    cache: Optional[ICacheService] = Depends(get_cache_service),
) -> SuggestNotesUseCase:
    return SuggestNotesUseCase(perfume_repository=perfume_repo, cache=cache)


def get_favorites_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
) -> GetFavoritesUseCase:
    return GetFavoritesUseCase(user_repository=user_repo)


def get_add_favorite_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
    perfume_repo: IPerfumeRepository = Depends(get_perfume_repository),
) -> AddFavoriteUseCase:
    return AddFavoriteUseCase(user_repository=user_repo, perfume_repository=perfume_repo)


def get_remove_favorite_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
) -> RemoveFavoriteUseCase:
    return RemoveFavoriteUseCase(user_repository=user_repo)


def get_search_history_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
) -> GetSearchHistoryUseCase:
    return GetSearchHistoryUseCase(user_repository=user_repo)


def get_delete_search_history_entry_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
) -> DeleteSearchHistoryEntryUseCase:
    return DeleteSearchHistoryEntryUseCase(user_repository=user_repo)


def get_clear_search_history_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
) -> ClearSearchHistoryUseCase:
    return ClearSearchHistoryUseCase(user_repository=user_repo)


def get_register_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
    email_service: IEmailService = Depends(get_email_service),
) -> RegisterUseCase:
    return RegisterUseCase(user_repo=user_repo, email_service=email_service)


def get_login_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
    email_service: IEmailService = Depends(get_email_service),
) -> LoginUseCase:
    return LoginUseCase(user_repo=user_repo, email_service=email_service)


def get_verify_code_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
    jwt_service: IJWTService = Depends(get_jwt_service),
) -> VerifyCodeUseCase:
    return VerifyCodeUseCase(user_repo=user_repo, jwt_service=jwt_service)


def get_refresh_token_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
    jwt_service: IJWTService = Depends(get_jwt_service),
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(user_repo=user_repo, jwt_service=jwt_service)


def get_logout_use_case(
    user_repo: IUserRepository = Depends(get_user_repository),
) -> LogoutUseCase:
    return LogoutUseCase(user_repo=user_repo)
