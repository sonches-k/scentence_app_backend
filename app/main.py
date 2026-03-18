"""
Главный файл приложения FastAPI.

Точка входа для сервера.
Использует Clean Architecture с разделением на слои:
- core: доменная логика и use cases
- infrastructure: БД, внешние сервисы
- api: HTTP интерфейс
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.infrastructure.config import settings
from app.api.routes import auth_router, search_router, perfumes_router, users_router

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
    """Корневой эндпоинт для проверки работоспособности API."""
    return {
        "message": "Perfume Selection API",
        "version": "0.1.0",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check эндпоинт."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
