"""
API Routes - HTTP эндпоинты.
"""

from app.api.routes.auth import router as auth_router
from app.api.routes.search import router as search_router
from app.api.routes.perfumes import router as perfumes_router
from app.api.routes.users import router as users_router

__all__ = [
    "auth_router",
    "search_router",
    "perfumes_router",
    "users_router",
]
