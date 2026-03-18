"""
Общие fixtures для всех тестов.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.entities import Perfume, User, UserFavorite, SearchHistoryEntry
from app.core.entities.perfume import Note, PerfumeNote, PerfumeWithRelevance
from app.core.interfaces import (
    IEmbeddingService,
    ILLMService,
    IPerfumeRepository,
    IUserRepository,
)
from app.core.use_cases import (
    FindSimilarUseCase,
    GetBrandsUseCase,
    GetFiltersUseCase,
    GetPerfumeUseCase,
    SemanticSearchUseCase,
    GetFavoritesUseCase,
    AddFavoriteUseCase,
    RemoveFavoriteUseCase,
    GetSearchHistoryUseCase,
)
from app.core.use_cases.perfume import FiltersData
from app.core.use_cases.search import SearchResult
from app.core.value_objects import NotePyramid
from app.main import app
from app.api.dependencies import (
    get_brands_use_case,
    get_filters_use_case,
    get_find_similar_use_case,
    get_optional_current_user,
    get_perfume_use_case,
    get_semantic_search_use_case,
    get_user_repository,
    get_favorites_use_case,
    get_add_favorite_use_case,
    get_remove_favorite_use_case,
    get_search_history_use_case,
    get_current_user,
)



@pytest.fixture
def sample_perfume() -> Perfume:
    return Perfume(
        id=1,
        name="Chanel No. 5",
        brand="Chanel",
        year=1921,
        product_type="EDP",
        family="Floral",
        gender="Female",
        description="Классический цветочный аромат с нотами альдегидов.",
        image_url="https://example.com/chanel5.jpg",
        notes=[
            PerfumeNote(note=Note(id=1, name="Бергамот",  category="Цитрусовые"), level="Top"),
            PerfumeNote(note=Note(id=2, name="Роза",      category="Цветочные"),  level="Middle"),
            PerfumeNote(note=Note(id=3, name="Мускус",    category="Мускусные"),  level="Base"),
        ],
        tags=[],
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        updated_at=None,
    )


@pytest.fixture
def sample_perfumes(sample_perfume) -> list[Perfume]:
    extras = [
        Perfume(
            id=i,
            name=f"Perfume {i}",
            brand=f"Brand {i}",
            family="Woody",
            gender="Unisex",
            notes=[],
            tags=[],
            created_at=datetime(2024, 1, 1),
        )
        for i in range(2, 6)
    ]
    return [sample_perfume] + extras


@pytest.fixture
def sample_user() -> User:
    return User(id=1, email="test@example.com", name="Тест")



@pytest.fixture
def mock_perfume_repository() -> MagicMock:
    return MagicMock(spec=IPerfumeRepository)


@pytest.fixture
def mock_user_repository() -> MagicMock:
    return MagicMock(spec=IUserRepository)


@pytest.fixture
def mock_embedding_service() -> MagicMock:
    mock = MagicMock(spec=IEmbeddingService)
    mock.generate_embedding.return_value = [0.1] * 312
    mock.generate_embeddings_batch.return_value = [[0.1] * 312]
    return mock


@pytest.fixture
def mock_llm_service() -> MagicMock:
    mock = MagicMock(spec=ILLMService)
    mock.extract_note_pyramid.return_value = NotePyramid(
        top=("Бергамот", "Лимон"),
        middle=("Роза", "Жасмин"),
        base=("Мускус", "Ваниль"),
    )
    mock.generate_search_explanation.return_value = "Тестовое пояснение к результатам поиска."
    return mock



@pytest.fixture
def test_client(sample_perfumes, sample_perfume):
    """
    FastAPI TestClient с подменёнными зависимостями.
    Не требует подключения к БД или внешним сервисам.
    """
    fixed_pyramid = NotePyramid(
        top=("Бергамот",),
        middle=("Роза",),
        base=("Мускус",),
    )

    mock_search_uc = MagicMock(spec=SemanticSearchUseCase)
    mock_search_uc.execute.return_value = SearchResult(
        query="тестовый запрос",
        note_pyramid=fixed_pyramid,
        explanation="Тестовое пояснение.",
        perfumes=[PerfumeWithRelevance(perfume=p, relevance=0.9) for p in sample_perfumes],
        filters_applied=None,
        total_found=len(sample_perfumes),
    )

    mock_similar_uc = MagicMock(spec=FindSimilarUseCase)
    mock_similar_uc.execute.return_value = [
        PerfumeWithRelevance(perfume=p, relevance=0.85) for p in sample_perfumes[:3]
    ]

    mock_perfume_uc = MagicMock(spec=GetPerfumeUseCase)
    mock_perfume_uc.execute.return_value = sample_perfume

    mock_filters_uc = MagicMock(spec=GetFiltersUseCase)
    mock_filters_uc.execute.return_value = FiltersData(
        genders=["Female", "Male", "Unisex"],
        families=["Floral", "Oriental", "Woody"],
        product_types=["EDP", "EDT", "Parfum"],
        brands=["Chanel", "Dior", "Guerlain"],
        notes=["Бергамот", "Роза", "Мускус", "Сандал"],
    )

    mock_brands_uc = MagicMock(spec=GetBrandsUseCase)
    mock_brands_uc.execute.return_value = ["Chanel", "Dior", "Guerlain"]

    mock_favorites_uc = MagicMock(spec=GetFavoritesUseCase)
    mock_favorites_uc.execute.return_value = sample_perfumes[:2]

    mock_add_fav_uc = MagicMock(spec=AddFavoriteUseCase)
    mock_add_fav_uc.execute.return_value = UserFavorite(id=1, user_id=1, perfume_id=1)

    mock_remove_fav_uc = MagicMock(spec=RemoveFavoriteUseCase)
    mock_remove_fav_uc.execute.return_value = True

    mock_history_uc = MagicMock(spec=GetSearchHistoryUseCase)
    mock_history_uc.execute.return_value = [
        SearchHistoryEntry(
            id=i, user_id=1, query_text=f"запрос {i}", created_at=datetime(2024, 1, i)
        )
        for i in range(1, 4)
    ]

    mock_user = User(id=1, email="test@example.com", name="Тест")

    app.dependency_overrides[get_semantic_search_use_case] = lambda: mock_search_uc
    app.dependency_overrides[get_find_similar_use_case]    = lambda: mock_similar_uc
    app.dependency_overrides[get_perfume_use_case]         = lambda: mock_perfume_uc
    app.dependency_overrides[get_filters_use_case]         = lambda: mock_filters_uc
    app.dependency_overrides[get_brands_use_case]          = lambda: mock_brands_uc
    app.dependency_overrides[get_favorites_use_case]       = lambda: mock_favorites_uc
    app.dependency_overrides[get_add_favorite_use_case]    = lambda: mock_add_fav_uc
    app.dependency_overrides[get_remove_favorite_use_case] = lambda: mock_remove_fav_uc
    app.dependency_overrides[get_search_history_use_case]  = lambda: mock_history_uc
    app.dependency_overrides[get_user_repository]          = lambda: MagicMock(spec=IUserRepository)
    app.dependency_overrides[get_optional_current_user]    = lambda: None
    app.dependency_overrides[get_current_user]             = lambda: mock_user

    client = TestClient(app, raise_server_exceptions=True)
    yield client

    app.dependency_overrides.clear()
