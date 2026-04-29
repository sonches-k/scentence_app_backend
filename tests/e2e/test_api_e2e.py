import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.e2e


class _MockLLMService:
    def generate_search_result(self, query: str, perfumes: list[dict]):
        from app.core.entities import NotePyramid
        return "Результаты подобраны для вашего запроса.", NotePyramid()


@pytest.fixture
def api_client(test_engine, seed_perfumes):
    """
    TestClient с тестовой БД и заглушками для embedding/LLM/cache.
    Позволяет тестировать HTTP-слой без загрузки тяжёлых моделей.
    """
    from sqlalchemy.orm import Session as SASession
    from app.infrastructure.database import get_db
    from app.infrastructure.database.models import Base as DBBase
    from app.api.dependencies import get_embedding_service, get_llm_service, get_cache_service
    from tests.e2e.conftest import FakeEmbeddingService

    # Гарантируем что схема существует перед каждым тестом
    DBBase.metadata.create_all(test_engine)

    def override_get_db():
        with SASession(test_engine) as session:
            yield session

    # lru_cache нужно сбросить, иначе overrides не заработают
    get_embedding_service.cache_clear()
    get_llm_service.cache_clear()
    get_cache_service.cache_clear()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    app.dependency_overrides[get_llm_service] = lambda: _MockLLMService()
    app.dependency_overrides[get_cache_service] = lambda: None

    client = TestClient(app, raise_server_exceptions=False)
    yield client

    app.dependency_overrides.clear()
    get_embedding_service.cache_clear()
    get_llm_service.cache_clear()
    get_cache_service.cache_clear()


def _get_verification_code(email: str, test_engine) -> str:
    """Читает код подтверждения напрямую из тестовой БД."""
    from sqlalchemy.orm import Session as SASession
    from app.infrastructure.database.repositories import SQLAlchemyUserRepository

    with SASession(test_engine) as session:
        repo = SQLAlchemyUserRepository(session)
        stored = repo.get_latest_verification_code(email)
        assert stored is not None, f"Код подтверждения для {email} не найден"
        return stored.code


class TestHealthEndpoints:

    def test_root(self, api_client):
        response = api_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "version" in data

    def test_health(self, api_client):
        response = api_client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestSearchAPIE2E:

    def test_semantic_search_full_pipeline(self, api_client):
        response = api_client.post(
            "/api/v1/search/",
            json={"query": "свежий цитрусовый аромат на лето", "limit": 3},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "свежий цитрусовый аромат на лето"
        assert data["total_found"] <= 3
        assert isinstance(data["explanation"], str)
        assert "top" in data["note_pyramid"]
        assert "middle" in data["note_pyramid"]
        assert "base" in data["note_pyramid"]
        for perfume in data["perfumes"]:
            assert "id" in perfume
            assert "name" in perfume
            assert 0.0 <= perfume["relevance"] <= 1.0

    def test_search_with_filters(self, api_client):
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
        """Короткий запрос (< 3 символов) → 422."""
        response = api_client.post(
            "/api/v1/search/",
            json={"query": "а"},
        )

        assert response.status_code == 422

    def test_similar_search(self, api_client, existing_perfume_id):
        response = api_client.post(f"/api/v1/search/similar/{existing_perfume_id}?limit=3")

        assert response.status_code == 200
        data = response.json()
        assert data["source_perfume_id"] == existing_perfume_id
        assert isinstance(data["similar_perfumes"], list)


class TestPerfumesAPIE2E:

    def test_get_perfume(self, api_client, existing_perfume_id):
        response = api_client.get(f"/api/v1/perfumes/{existing_perfume_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == existing_perfume_id
        assert "name" in data
        assert "brand" in data
        assert "notes" in data

    def test_get_perfume_not_found(self, api_client):
        response = api_client.get("/api/v1/perfumes/999999")

        assert response.status_code == 404

    def test_get_filters(self, api_client):
        """GET /api/v1/perfumes/filters → непустые списки фильтров."""
        response = api_client.get("/api/v1/perfumes/filters")

        assert response.status_code == 200
        data = response.json()
        assert len(data["genders"]) > 0
        assert len(data["families"]) > 0
        assert len(data["categories"]) > 0

    def test_suggest_brands(self, api_client):
        """GET /api/v1/perfumes/brands/suggest → список строк."""
        response = api_client.get("/api/v1/perfumes/brands/suggest")

        assert response.status_code == 200
        brands = response.json()
        assert isinstance(brands, list)
        assert len(brands) > 0


class TestAuthAPIE2E:

    def test_register_and_verify(self, api_client, test_engine):
        import uuid
        email = f"api_{uuid.uuid4().hex[:8]}@example.com"

        response = api_client.post("/api/v1/auth/register", json={"email": email})
        assert response.status_code == 200

        code = _get_verification_code(email, test_engine)

        response = api_client.post(
            "/api/v1/auth/verify",
            json={"email": email, "code": code},
        )
        assert response.status_code == 200
        data = response.json()
        token = data["access_token"]
        assert len(token) > 20
        assert "refresh_token" in data

        response = api_client.get(
            "/api/v1/users/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["email"] == email

    def test_login_nonexistent_user(self, api_client):
        response = api_client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent_999@example.com"},
        )

        assert response.status_code == 404

    def test_verify_wrong_code(self, api_client):
        import uuid
        email = f"wrong_{uuid.uuid4().hex[:8]}@example.com"
        api_client.post("/api/v1/auth/register", json={"email": email})

        response = api_client.post(
            "/api/v1/auth/verify",
            json={"email": email, "code": "000000"},
        )
        assert response.status_code == 401

    def test_logout(self, api_client, test_engine):
        import uuid
        email = f"logout_{uuid.uuid4().hex[:8]}@example.com"
        api_client.post("/api/v1/auth/register", json={"email": email})

        code = _get_verification_code(email, test_engine)

        verify = api_client.post(
            "/api/v1/auth/verify",
            json={"email": email, "code": code},
        )
        assert verify.status_code == 200
        refresh = verify.json()["refresh_token"]

        response = api_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh},
        )
        assert response.status_code == 200


class TestUsersAPIE2E:

    @pytest.fixture
    def auth_headers(self, api_client, test_engine):
        import uuid
        email = f"user_{uuid.uuid4().hex[:8]}@example.com"

        api_client.post("/api/v1/auth/register", json={"email": email})
        code = _get_verification_code(email, test_engine)

        response = api_client.post(
            "/api/v1/auth/verify",
            json={"email": email, "code": code},
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_favorites_workflow(self, api_client, auth_headers, existing_perfume_id):
        pid = existing_perfume_id

        response = api_client.post(f"/api/v1/users/favorites/{pid}", headers=auth_headers)
        assert response.status_code == 201

        response = api_client.get("/api/v1/users/favorites", headers=auth_headers)
        assert response.status_code == 200
        assert any(p["id"] == pid for p in response.json())

        response = api_client.delete(f"/api/v1/users/favorites/{pid}", headers=auth_headers)
        assert response.status_code == 200

    def test_search_history(self, api_client, auth_headers):
        api_client.post(
            "/api/v1/search/",
            json={"query": "тёплый аромат с ванилью", "limit": 3},
            headers=auth_headers,
        )

        response = api_client.get("/api/v1/users/history", headers=auth_headers)
        assert response.status_code == 200
        history = response.json()
        assert any(h["query"] == "тёплый аромат с ванилью" for h in history)

    def test_unauthorized_access(self, api_client):
        assert api_client.get("/api/v1/users/favorites").status_code == 401
        assert api_client.get("/api/v1/users/profile").status_code == 401
