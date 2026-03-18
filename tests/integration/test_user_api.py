"""
Integration-тесты для эндпоинтов /users/.
Используют FastAPI TestClient с подменёнными зависимостями (без БД).
"""

import pytest
from unittest.mock import MagicMock

from app.core.exceptions import UserNotFoundError
from app.core.use_cases import GetFavoritesUseCase
from app.main import app
from app.api.dependencies import get_favorites_use_case, get_current_user


pytestmark = pytest.mark.integration

BASE = "/api/v1"


class TestGetFavoritesEndpoint:

    def test_get_favorites_success(self, test_client):
        """GET /users/favorites → 200 и список карточек."""
        response = test_client.get(f"{BASE}/users/favorites")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_get_favorites_has_card_fields(self, test_client):
        """Каждая карточка содержит основные поля."""
        response = test_client.get(f"{BASE}/users/favorites")

        assert response.status_code == 200
        card = response.json()[0]
        assert "id" in card
        assert "name" in card
        assert "brand" in card
        assert "top_notes" in card
        assert "middle_notes" in card
        assert "base_notes" in card


class TestAddFavoriteEndpoint:

    def test_add_favorite_success(self, test_client):
        """POST /users/favorites/{id} → 201."""
        response = test_client.post(f"{BASE}/users/favorites/1")

        assert response.status_code == 201
        data = response.json()
        assert "message" in data
        assert "id" in data

    def test_add_favorite_returns_id(self, test_client):
        """Ответ содержит ID созданного избранного."""
        response = test_client.post(f"{BASE}/users/favorites/10")

        assert response.status_code == 201
        assert response.json()["id"] == 1  # from mock


class TestRemoveFavoriteEndpoint:

    def test_remove_favorite_success(self, test_client):
        """DELETE /users/favorites/{id} → 200."""
        response = test_client.delete(f"{BASE}/users/favorites/1")

        assert response.status_code == 200
        assert "message" in response.json()

    def test_remove_favorite_not_found(self, test_client):
        """Аромат не в избранном — 404."""
        mock_uc = MagicMock()
        mock_uc.execute.return_value = False

        from app.api.dependencies import get_remove_favorite_use_case
        app.dependency_overrides[get_remove_favorite_use_case] = lambda: mock_uc
        try:
            response = test_client.delete(f"{BASE}/users/favorites/999")
        finally:
            app.dependency_overrides.pop(get_remove_favorite_use_case, None)

        assert response.status_code == 404


class TestGetHistoryEndpoint:

    def test_get_history_success(self, test_client):
        """GET /users/history → 200 и список записей."""
        response = test_client.get(f"{BASE}/users/history")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

    def test_get_history_entry_structure(self, test_client):
        """Каждая запись содержит id, query, filters, created_at."""
        response = test_client.get(f"{BASE}/users/history")

        assert response.status_code == 200
        entry = response.json()[0]
        assert "id" in entry
        assert "query" in entry
        assert "created_at" in entry


class TestProfileEndpoint:

    def test_get_profile_success(self, test_client):
        """GET /users/profile → 200 и данные профиля."""
        response = test_client.get(f"{BASE}/users/profile")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["email"] == "test@example.com"
        assert data["name"] == "Тест"

    def test_get_profile_unauthorized(self, test_client):
        """GET /users/profile без токена → 401."""
        # Убираем mock для get_current_user чтобы сработала настоящая проверка
        from app.api.dependencies import get_current_user as dep_fn
        original = app.dependency_overrides.get(dep_fn)
        app.dependency_overrides.pop(dep_fn, None)
        try:
            client = test_client  # reuse client, overrides already changed
            response = test_client.get(f"{BASE}/users/profile")
            # Без токена должен быть 401 (HTTPBearer auto_error=False → наш код кидает 401)
            assert response.status_code == 401
        finally:
            if original is not None:
                app.dependency_overrides[dep_fn] = original
