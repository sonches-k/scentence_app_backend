"""
E2E-тесты API через TestClient с реальными сервисами.

Запуск: pytest tests/e2e/test_api_e2e.py -v
Требует: PostgreSQL с данными, DeepSeek API, sentence-transformers.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.e2e


@pytest.fixture
def api_client():
    """
    TestClient БЕЗ подмены зависимостей — все реальное.
    """
    app.dependency_overrides.clear()
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


class TestHealthEndpoints:

    def test_root(self, api_client):
        """GET / → 200 и метаданные."""
        response = api_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "version" in data

    def test_health(self, api_client):
        """GET /health → 200."""
        response = api_client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestSearchAPIE2E:

    def test_semantic_search_full_pipeline(self, api_client):
        """
        POST /api/v1/search/ → реальный embedding + pgvector + DeepSeek.
        Самый важный E2E тест — проверяет весь RAG-пайплайн через HTTP.
        """
        response = api_client.post(
            "/api/v1/search/",
            json={"query": "свежий цитрусовый аромат на лето", "limit": 3},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "свежий цитрусовый аромат на лето"
        assert data["total_found"] <= 3
        assert len(data["explanation"]) > 10

        # Пирамида нот
        pyramid = data["note_pyramid"]
        assert "top" in pyramid
        assert "middle" in pyramid
        assert "base" in pyramid

        # Ароматы с релевантностью
        for perfume in data["perfumes"]:
            assert "id" in perfume
            assert "name" in perfume
            assert "brand" in perfume
            assert 0.0 <= perfume["relevance"] <= 1.0

    def test_search_with_filters(self, api_client):
        """Поиск с фильтрами — все результаты соответствуют."""
        response = api_client.post(
            "/api/v1/search/",
            json={
                "query": "нежный цветочный аромат",
                "filters": {"genders": ["Female"]},
                "limit": 5,
            },
        )

        assert response.status_code == 200
        for perfume in response.json()["perfumes"]:
            assert perfume["gender"] == "Female"

    def test_search_validation(self, api_client):
        """Короткий запрос → 422."""
        response = api_client.post(
            "/api/v1/search/",
            json={"query": "а"},
        )

        assert response.status_code == 422

    def test_similar_search(self, api_client, existing_perfume_id):
        """POST /api/v1/search/similar/{id} → похожие ароматы."""
        pid = existing_perfume_id
        response = api_client.post(f"/api/v1/search/similar/{pid}?limit=3")

        assert response.status_code == 200
        data = response.json()
        assert data["source_perfume_id"] == pid
        assert isinstance(data["similar_perfumes"], list)


class TestPerfumesAPIE2E:

    def test_get_perfume(self, api_client, existing_perfume_id):
        """GET /api/v1/perfumes/{id} → полные данные."""
        pid = existing_perfume_id
        response = api_client.get(f"/api/v1/perfumes/{pid}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == pid
        assert "name" in data
        assert "brand" in data
        assert "notes" in data
        assert "tags" in data

    def test_get_perfume_not_found(self, api_client):
        """GET /api/v1/perfumes/999999 → 404."""
        response = api_client.get("/api/v1/perfumes/999999")

        assert response.status_code == 404

    def test_get_filters(self, api_client):
        """GET /api/v1/perfumes/filters/all → непустые списки."""
        response = api_client.get("/api/v1/perfumes/filters/all")

        assert response.status_code == 200
        data = response.json()
        assert len(data["genders"]) > 0
        assert len(data["families"]) > 0
        assert len(data["brands"]) > 0

    def test_get_brands(self, api_client):
        """GET /api/v1/perfumes/brands/all → список строк."""
        response = api_client.get("/api/v1/perfumes/brands/all")

        assert response.status_code == 200
        brands = response.json()
        assert isinstance(brands, list)
        assert len(brands) > 0


class TestAuthAPIE2E:

    def test_register_and_verify(self, api_client):
        """Полный auth flow: register → verify → получение профиля."""
        import uuid
        email = f"api_{uuid.uuid4().hex[:8]}@example.com"

        response = api_client.post(
            "/api/v1/auth/register",
            json={"email": email},
        )
        assert response.status_code == 200

        from app.infrastructure.database.connection import SessionLocal
        from app.infrastructure.database.repositories import SQLAlchemyUserRepository
        session = SessionLocal()
        try:
            repo = SQLAlchemyUserRepository(session)
            stored = repo.get_latest_verification_code(email)
            assert stored is not None
            code = stored.code
        finally:
            session.close()

        response = api_client.post(
            "/api/v1/auth/verify",
            json={"email": email, "code": code},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        assert len(token) > 20

        response = api_client.get(
            "/api/v1/users/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["email"] == email

    def test_login_nonexistent_user(self, api_client):
        """Login несуществующего пользователя → 404."""
        response = api_client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent_999@example.com"},
        )

        assert response.status_code == 404

    def test_verify_wrong_code(self, api_client):
        """Неверный код → 401."""
        import uuid
        email = f"wrong_{uuid.uuid4().hex[:8]}@example.com"

        api_client.post("/api/v1/auth/register", json={"email": email})

        response = api_client.post(
            "/api/v1/auth/verify",
            json={"email": email, "code": "000000"},
        )
        assert response.status_code == 401

    def test_logout(self, api_client):
        """POST /auth/logout → 200 (stateless)."""
        response = api_client.post("/api/v1/auth/logout")

        assert response.status_code == 200


class TestUsersAPIE2E:

    @pytest.fixture
    def auth_headers(self, api_client):
        """Создаёт пользователя и возвращает заголовки с JWT."""
        import uuid
        email = f"user_{uuid.uuid4().hex[:8]}@example.com"

        api_client.post("/api/v1/auth/register", json={"email": email})

        from app.infrastructure.database.connection import SessionLocal
        from app.infrastructure.database.repositories import SQLAlchemyUserRepository
        session = SessionLocal()
        try:
            repo = SQLAlchemyUserRepository(session)
            stored = repo.get_latest_verification_code(email)
            code = stored.code
        finally:
            session.close()

        response = api_client.post(
            "/api/v1/auth/verify",
            json={"email": email, "code": code},
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_favorites_workflow(self, api_client, auth_headers, existing_perfume_id):
        """Добавить → получить → удалить избранное через API."""
        pid = existing_perfume_id
        response = api_client.post(
            f"/api/v1/users/favorites/{pid}",
            headers=auth_headers,
        )
        assert response.status_code == 201

        response = api_client.get(
            "/api/v1/users/favorites",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert any(p["id"] == pid for p in response.json())

        response = api_client.delete(
            f"/api/v1/users/favorites/{pid}",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_search_history(self, api_client, auth_headers):
        """Поиск с токеном → запись в историю → GET history."""
        api_client.post(
            "/api/v1/search/",
            json={"query": "тёплый аромат с ванилью", "limit": 3},
            headers=auth_headers,
        )

        response = api_client.get(
            "/api/v1/users/history",
            headers=auth_headers,
        )
        assert response.status_code == 200
        history = response.json()
        assert any(h["query"] == "тёплый аромат с ванилью" for h in history)

    def test_unauthorized_access(self, api_client):
        """Доступ без токена → 401."""
        response = api_client.get("/api/v1/users/favorites")
        assert response.status_code == 401

        response = api_client.get("/api/v1/users/profile")
        assert response.status_code == 401
