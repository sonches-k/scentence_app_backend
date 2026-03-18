"""
Integration-тесты для эндпоинтов /perfumes/.
Используют FastAPI TestClient с подменёнными зависимостями (без БД).
"""

import pytest
from unittest.mock import MagicMock

from app.core.exceptions import PerfumeNotFoundError
from app.main import app
from app.api.dependencies import get_perfume_use_case


pytestmark = pytest.mark.integration

BASE = "/api/v1"


class TestGetPerfumeEndpoint:

    def test_get_perfume_success(self, test_client):
        """GET /perfumes/{id} → 200 и полные данные аромата."""
        response = test_client.get(f"{BASE}/perfumes/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Chanel No. 5"
        assert data["brand"] == "Chanel"
        assert "notes" in data
        assert "tags" in data
        assert "created_at" in data

    def test_get_perfume_response_has_notes(self, test_client):
        """Ответ содержит список нот."""
        response = test_client.get(f"{BASE}/perfumes/1")

        assert response.status_code == 200
        notes = response.json()["notes"]
        assert isinstance(notes, list)
        assert len(notes) == 3  # Бергамот, Роза, Мускус

    def test_get_perfume_not_found(self, test_client):
        """GET /perfumes/{id} несуществующего ID → 404."""
        mock_uc = MagicMock()
        mock_uc.execute.side_effect = PerfumeNotFoundError("not found")

        app.dependency_overrides[get_perfume_use_case] = lambda: mock_uc
        try:
            response = test_client.get(f"{BASE}/perfumes/99999")
        finally:
            # Восстанавливаем исходный override из test_client fixture
            app.dependency_overrides.pop(get_perfume_use_case, None)

        assert response.status_code == 404
        assert "99999" in response.json()["detail"]

    def test_get_perfume_invalid_id_type(self, test_client):
        """Нечисловой ID → 422."""
        response = test_client.get(f"{BASE}/perfumes/abc")

        assert response.status_code == 422


class TestGetFiltersEndpoint:

    def test_get_filters_success(self, test_client):
        """GET /perfumes/filters/all → 200 и структура фильтров."""
        response = test_client.get(f"{BASE}/perfumes/filters/all")

        assert response.status_code == 200
        data = response.json()
        assert "genders" in data
        assert "families" in data
        assert "product_types" in data
        assert "brands" in data
        assert "notes" in data

    def test_get_filters_returns_lists(self, test_client):
        """Все поля фильтров — списки."""
        response = test_client.get(f"{BASE}/perfumes/filters/all")

        assert response.status_code == 200
        data = response.json()
        for key in ("genders", "families", "product_types", "brands", "notes"):
            assert isinstance(data[key], list), f"{key} должен быть списком"

    def test_get_filters_content(self, test_client):
        """Фильтры содержат ожидаемые значения из mock."""
        response = test_client.get(f"{BASE}/perfumes/filters/all")

        assert response.status_code == 200
        data = response.json()
        assert "Female" in data["genders"]
        assert "Chanel" in data["brands"]
        assert "Floral" in data["families"]


class TestGetBrandsEndpoint:

    def test_get_brands_success(self, test_client):
        """GET /perfumes/brands/all → 200 и список строк."""
        response = test_client.get(f"{BASE}/perfumes/brands/all")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert all(isinstance(b, str) for b in data)

    def test_get_brands_content(self, test_client):
        """Список брендов содержит ожидаемые значения."""
        response = test_client.get(f"{BASE}/perfumes/brands/all")

        assert response.status_code == 200
        brands = response.json()
        assert "Chanel" in brands
        assert "Dior" in brands
