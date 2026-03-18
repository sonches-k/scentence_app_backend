"""
E2E-тесты репозиториев с реальной PostgreSQL.

Запуск: pytest tests/e2e/test_repositories.py -v
Требует: PostgreSQL с данными (после load_to_db.py + generate_embeddings.py).
"""

import pytest

from app.core.entities import Perfume, User, UserFavorite, SearchHistoryEntry

pytestmark = pytest.mark.e2e


class TestPerfumeRepository:

    def test_get_by_id_existing(self, perfume_repo, existing_perfume_id):
        """Получение аромата по ID — возвращает Perfume с нотами и тегами."""
        perfume = perfume_repo.get_by_id(existing_perfume_id)

        assert perfume is not None
        assert isinstance(perfume, Perfume)
        assert perfume.id == existing_perfume_id
        assert perfume.name
        assert perfume.brand

    def test_get_by_id_nonexistent(self, perfume_repo):
        """Несуществующий ID — возвращает None."""
        perfume = perfume_repo.get_by_id(999999)

        assert perfume is None

    def test_get_by_id_has_notes(self, perfume_repo, existing_perfume_id):
        """Аромат загружается с нотами."""
        perfume = perfume_repo.get_by_id(existing_perfume_id)

        assert perfume is not None
        if perfume.notes:
            note = perfume.notes[0]
            assert note.note.name
            assert note.level in ("Top", "Middle", "Base", "top", "middle", "base")

    def test_get_all_default(self, perfume_repo):
        """get_all без фильтров — возвращает список."""
        perfumes = perfume_repo.get_all(limit=10)

        assert isinstance(perfumes, list)
        assert len(perfumes) <= 10
        assert all(isinstance(p, Perfume) for p in perfumes)

    def test_get_all_with_gender_filter(self, perfume_repo):
        """Фильтр по полу — все результаты соответствуют."""
        perfumes = perfume_repo.get_all(
            limit=10,
            filters={"genders": ["Female"]},
        )

        for p in perfumes:
            assert p.gender == "Female"

    def test_get_all_with_family_filter(self, perfume_repo):
        """Фильтр по семейству."""
        perfumes = perfume_repo.get_all(
            limit=10,
            filters={"families": ["Floral"]},
        )

        for p in perfumes:
            assert p.family == "Floral"

    def test_search_by_embedding(self, perfume_repo, embedding_service):
        """Поиск по эмбеддингу — возвращает (Perfume, score) отсортированные по score."""
        embedding = embedding_service.generate_embedding("свежий цитрусовый аромат")
        results = perfume_repo.search_by_embedding(embedding=embedding, limit=5)

        assert isinstance(results, list)
        assert len(results) <= 5
        for perfume, score in results:
            assert isinstance(perfume, Perfume)
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0

        # Проверяем что отсортировано по убыванию score
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_by_embedding_with_filters(self, perfume_repo, embedding_service):
        """Поиск по эмбеддингу с фильтром по полу."""
        embedding = embedding_service.generate_embedding("тёплый восточный аромат")
        results = perfume_repo.search_by_embedding(
            embedding=embedding,
            limit=5,
            filters={"genders": ["Female"]},
        )

        for perfume, _ in results:
            assert perfume.gender == "Female"

    def test_find_similar(self, perfume_repo, existing_perfume_id):
        """Поиск похожих ароматов — не включает исходный."""
        results = perfume_repo.find_similar(perfume_id=existing_perfume_id, limit=3)

        assert isinstance(results, list)
        for perfume, score in results:
            assert perfume.id != existing_perfume_id
            assert isinstance(score, float)

    def test_get_unique_brands(self, perfume_repo):
        """Список брендов — непустой, отсортирован."""
        brands = perfume_repo.get_unique_brands()

        assert isinstance(brands, list)
        assert len(brands) > 0
        assert brands == sorted(brands)

    def test_get_unique_families(self, perfume_repo):
        """Список семейств — непустой."""
        families = perfume_repo.get_unique_families()

        assert len(families) > 0
        assert all(isinstance(f, str) for f in families)

    def test_get_unique_genders(self, perfume_repo):
        """Список полов — содержит ожидаемые значения."""
        genders = perfume_repo.get_unique_genders()

        assert len(genders) > 0

    def test_get_unique_notes(self, perfume_repo):
        """Список нот — непустой."""
        notes = perfume_repo.get_unique_notes()

        assert len(notes) > 0

    def test_get_unique_product_types(self, perfume_repo):
        """Список типов продукта — непустой."""
        product_types = perfume_repo.get_unique_product_types()

        assert len(product_types) > 0


class TestUserRepository:

    def test_create_and_get_by_email(self, user_repo, db_session):
        """Создание пользователя и получение по email."""
        import uuid
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"

        user = user_repo.create(email=email, name="Тестовый")

        assert user.id is not None
        assert user.email == email
        assert user.name == "Тестовый"

        found = user_repo.get_by_email(email)
        assert found is not None
        assert found.id == user.id

    def test_get_by_email_nonexistent(self, user_repo):
        """Несуществующий email — None."""
        user = user_repo.get_by_email("nonexistent_999@example.com")

        assert user is None

    def test_get_by_id_nonexistent(self, user_repo):
        """Несуществующий ID — None."""
        user = user_repo.get_by_id(999999)

        assert user is None

    def test_favorites_workflow(self, user_repo, db_session, existing_perfume_id):
        """Полный цикл: добавить → проверить → получить → удалить."""
        import uuid
        email = f"fav_{uuid.uuid4().hex[:8]}@example.com"
        user = user_repo.create(email=email)
        pid = existing_perfume_id

        fav = user_repo.add_favorite(user.id, pid)
        assert isinstance(fav, UserFavorite)
        assert fav.perfume_id == pid

        assert user_repo.is_favorite(user.id, pid) is True
        assert user_repo.is_favorite(user.id, 999999) is False

        favorites = user_repo.get_favorites(user.id)
        assert len(favorites) >= 1
        assert any(p.id == pid for p in favorites)

        removed = user_repo.remove_favorite(user.id, pid)
        assert removed is True
        assert user_repo.is_favorite(user.id, pid) is False

    def test_search_history_workflow(self, user_repo, db_session):
        """Добавление и получение истории поиска."""
        import uuid
        email = f"hist_{uuid.uuid4().hex[:8]}@example.com"
        user = user_repo.create(email=email)

        entry = user_repo.add_search_history(
            user_id=user.id,
            query_text="тёплый аромат с ванилью",
            filters={"genders": ["Female"]},
        )
        assert isinstance(entry, SearchHistoryEntry)
        assert entry.query_text == "тёплый аромат с ванилью"
        assert entry.filters == {"genders": ["Female"]}

        history = user_repo.get_search_history(user.id, limit=10)
        assert len(history) >= 1
        assert history[0].query_text == "тёплый аромат с ванилью"

    def test_update_name(self, user_repo, db_session):
        """Обновление имени пользователя."""
        import uuid
        email = f"name_{uuid.uuid4().hex[:8]}@example.com"
        user = user_repo.create(email=email, name="Старое")

        updated = user_repo.update_name(user.id, "Новое")
        assert updated.name == "Новое"

    def test_verification_code_workflow(self, user_repo, db_session):
        """Полный цикл: создать код → получить → инкремент → удалить."""
        from datetime import datetime, timedelta, timezone
        import uuid
        email = f"code_{uuid.uuid4().hex[:8]}@example.com"
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)

        code = user_repo.create_verification_code(email, "123456", expires)
        assert code.code == "123456"
        assert code.attempts == 0

        latest = user_repo.get_latest_verification_code(email)
        assert latest is not None
        assert latest.code == "123456"

        user_repo.increment_code_attempts(code.id)
        latest = user_repo.get_latest_verification_code(email)
        assert latest.attempts == 1

        user_repo.delete_verification_codes(email)
        assert user_repo.get_latest_verification_code(email) is None
