"""
Integration-тесты для эндпоинтов поиска.
Используют FastAPI TestClient с подменёнными зависимостями (без БД).
"""

import pytest
from unittest.mock import MagicMock

from app.core.exceptions import PerfumeNotFoundError
from app.main import app
from app.api.dependencies import get_find_similar_use_case


pytestmark = pytest.mark.integration

BASE = "/api/v1"


class TestSemanticSearchEndpoint:

    def test_search_endpoint_success(self, test_client):
        """POST /search/ с валидным запросом → 200 и корректная структура."""
        response = test_client.post(
            f"{BASE}/search/",
            json={"query": "тёплый восточный аромат с ванилью", "limit": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "note_pyramid" in data
        assert "explanation" in data
        assert "perfumes" in data
        assert "total_found" in data
        assert isinstance(data["perfumes"], list)

    def test_search_endpoint_note_pyramid_structure(self, test_client):
        """Ответ содержит пирамиду нот с полями top, middle, base."""
        response = test_client.post(
            f"{BASE}/search/",
            json={"query": "свежий цитрусовый аромат"},
        )

        assert response.status_code == 200
        pyramid = response.json()["note_pyramid"]
        assert "top" in pyramid
        assert "middle" in pyramid
        assert "base" in pyramid
        assert isinstance(pyramid["top"], list)
        assert isinstance(pyramid["middle"], list)
        assert isinstance(pyramid["base"], list)

    def test_search_endpoint_empty_query_rejected(self, test_client):
        """Пустой запрос → 422 (Pydantic validation)."""
        response = test_client.post(
            f"{BASE}/search/",
            json={"query": ""},
        )

        assert response.status_code == 422

    def test_search_endpoint_short_query_rejected(self, test_client):
        """Запрос короче 3 символов → 422."""
        response = test_client.post(
            f"{BASE}/search/",
            json={"query": "аб"},
        )

        assert response.status_code == 422

    def test_search_endpoint_long_query_rejected(self, test_client):
        """Запрос длиннее 1000 символов → 422."""
        response = test_client.post(
            f"{BASE}/search/",
            json={"query": "а" * 1001},
        )

        assert response.status_code == 422

    def test_search_endpoint_missing_query_rejected(self, test_client):
        """Запрос без поля query → 422."""
        response = test_client.post(
            f"{BASE}/search/",
            json={"limit": 5},
        )

        assert response.status_code == 422

    def test_search_endpoint_with_filters(self, test_client):
        """POST /search/ с фильтрами → 200."""
        response = test_client.post(
            f"{BASE}/search/",
            json={
                "query": "цветочный женский аромат",
                "filters": {
                    "genders": ["Female"],
                    "families": ["Floral"],
                },
                "limit": 3,
            },
        )

        assert response.status_code == 200

    def test_search_endpoint_limit_too_large(self, test_client):
        """limit > 20 → 422 (Pydantic validation)."""
        response = test_client.post(
            f"{BASE}/search/",
            json={"query": "тест", "limit": 100},
        )

        assert response.status_code == 422

    def test_search_endpoint_default_limit(self, test_client):
        """Запрос без limit — используется дефолтное значение."""
        response = test_client.post(
            f"{BASE}/search/",
            json={"query": "мускусный аромат"},
        )

        assert response.status_code == 200


class TestFindSimilarEndpoint:

    def test_similar_endpoint_success(self, test_client):
        """POST /search/similar/{id} → 200 и список похожих."""
        response = test_client.post(f"{BASE}/search/similar/1")

        assert response.status_code == 200
        data = response.json()
        assert "source_perfume_id" in data
        assert "similar_perfumes" in data
        assert data["source_perfume_id"] == 1
        assert isinstance(data["similar_perfumes"], list)

    def test_similar_endpoint_perfumes_have_relevance(self, test_client):
        """Каждый аромат в ответе содержит поле relevance."""
        response = test_client.post(f"{BASE}/search/similar/1")

        assert response.status_code == 200
        perfumes = response.json()["similar_perfumes"]
        for p in perfumes:
            assert "relevance" in p
            assert 0.0 <= p["relevance"] <= 1.0

    def test_similar_endpoint_with_limit(self, test_client):
        """POST /search/similar/{id}?limit=3 → 200."""
        response = test_client.post(f"{BASE}/search/similar/1?limit=3")

        assert response.status_code == 200

    def test_similar_endpoint_invalid_id_type(self, test_client):
        """Не числовой ID → 422."""
        response = test_client.post(f"{BASE}/search/similar/abc")

        assert response.status_code == 422

    def test_similar_endpoint_perfume_not_found(self, test_client):
        """Несуществующий perfume_id → 404 с сообщением Perfume not found."""
        mock_uc = MagicMock()
        mock_uc.execute.side_effect = PerfumeNotFoundError("Perfume with id=999 not found")

        app.dependency_overrides[get_find_similar_use_case] = lambda: mock_uc
        try:
            response = test_client.post(f"{BASE}/search/similar/999")
        finally:
            app.dependency_overrides.pop(get_find_similar_use_case, None)

        assert response.status_code == 404
        assert response.json()["detail"] == "Perfume not found"

    def test_similar_endpoint_limit_too_large(self, test_client):
        """limit > 20 → 422 (валидация Query)."""
        response = test_client.post(f"{BASE}/search/similar/1?limit=21")

        assert response.status_code == 422

    def test_similar_endpoint_limit_zero(self, test_client):
        """limit < 1 → 422 (валидация Query)."""
        response = test_client.post(f"{BASE}/search/similar/1?limit=0")

        assert response.status_code == 422


class TestSearchFiltersValidation:

    def test_year_from_greater_than_year_to_rejected(self, test_client):
        """year_from > year_to → 422."""
        response = test_client.post(
            f"{BASE}/search/",
            json={
                "query": "цветочный аромат",
                "filters": {"year_from": 2024, "year_to": 2010},
            },
        )
        assert response.status_code == 422

    def test_year_from_equal_year_to_accepted(self, test_client):
        """year_from == year_to → 200."""
        response = test_client.post(
            f"{BASE}/search/",
            json={
                "query": "цветочный аромат",
                "filters": {"year_from": 2020, "year_to": 2020},
            },
        )
        assert response.status_code == 200

    def test_year_from_less_than_year_to_accepted(self, test_client):
        """year_from < year_to → 200."""
        response = test_client.post(
            f"{BASE}/search/",
            json={
                "query": "цветочный аромат",
                "filters": {"year_from": 2010, "year_to": 2024},
            },
        )
        assert response.status_code == 200

    def test_year_from_below_min_rejected(self, test_client):
        """year_from < 1800 → 422."""
        response = test_client.post(
            f"{BASE}/search/",
            json={
                "query": "цветочный аромат",
                "filters": {"year_from": 1799},
            },
        )
        assert response.status_code == 422

    def test_year_to_above_max_rejected(self, test_client):
        """year_to > 2030 → 422."""
        response = test_client.post(
            f"{BASE}/search/",
            json={
                "query": "цветочный аромат",
                "filters": {"year_to": 2031},
            },
        )
        assert response.status_code == 422
