import logging

from fastapi import FastAPI, Request
from fastapi import status as http_status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.infrastructure.config import settings
from app.api.routes import auth_router, search_router, perfumes_router, users_router

limiter = Limiter(key_func=get_remote_address)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(name)s - %(message)s",
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="API для подбора парфюмерии на основе семантических профилей",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    auth_router,
    prefix=f"{settings.API_V1_PREFIX}/auth",
    tags=["auth"],
)

app.include_router(
    search_router,
    prefix=f"{settings.API_V1_PREFIX}/search",
    tags=["search"],
)

app.include_router(
    perfumes_router,
    prefix=f"{settings.API_V1_PREFIX}/perfumes",
    tags=["perfumes"],
)

app.include_router(
    users_router,
    prefix=f"{settings.API_V1_PREFIX}/users",
    tags=["users"],
)


@app.get("/")
async def root():
    return {
        "message": "Perfume Selection API",
        "version": "0.1.0",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    from sqlalchemy import text
    from app.infrastructure.database.connection import get_db

    db_status = "ok"
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"

    redis_status = "ok"
    if settings.REDIS_URL:
        try:
            from app.infrastructure.cache.redis_service import RedisCacheService
            RedisCacheService(settings.REDIS_URL)._client.ping()
        except Exception:
            redis_status = "unavailable"
    else:
        redis_status = "not configured"

    is_healthy = db_status == "ok"
    return JSONResponse(
        status_code=http_status.HTTP_200_OK if is_healthy else http_status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if is_healthy else "unhealthy",
            "db": db_status,
            "redis": redis_status,
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
