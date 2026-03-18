"""
Unit-тесты для value objects: NotePyramid, PerfumeTag, SearchFilters.
"""

import pytest

from app.core.value_objects.perfume import NotePyramid, PerfumeTag
from app.core.value_objects.search import SearchFilters


pytestmark = pytest.mark.unit


class TestNotePyramid:

    def test_creation_with_lists(self):
        """Создание из списков — конвертирует в tuple."""
        pyramid = NotePyramid(
            top=["Бергамот", "Лимон"],
            middle=["Роза"],
            base=["Мускус", "Ваниль"],
        )

        assert pyramid.top == ("Бергамот", "Лимон")
        assert pyramid.middle == ("Роза",)
        assert pyramid.base == ("Мускус", "Ваниль")

    def test_creation_empty(self):
        """Создание без аргументов — пустые tuple."""
        pyramid = NotePyramid()

        assert pyramid.top == ()
        assert pyramid.middle == ()
        assert pyramid.base == ()

    def test_immutability(self):
        """Frozen dataclass — нельзя изменять атрибуты."""
        pyramid = NotePyramid(top=["Бергамот"], middle=["Роза"], base=["Мускус"])

        with pytest.raises(AttributeError):
            pyramid.top = ("Лимон",)

    def test_to_lists(self):
        """to_lists() возвращает dict со списками."""
        pyramid = NotePyramid(
            top=["Бергамот"],
            middle=["Роза", "Жасмин"],
            base=["Мускус"],
        )

        result = pyramid.to_lists()

        assert result == {
            "top": ["Бергамот"],
            "middle": ["Роза", "Жасмин"],
            "base": ["Мускус"],
        }
        assert isinstance(result["top"], list)

    def test_equality(self):
        """Два NotePyramid с одинаковым содержимым равны."""
        p1 = NotePyramid(top=["A"], middle=["B"], base=["C"])
        p2 = NotePyramid(top=["A"], middle=["B"], base=["C"])

        assert p1 == p2


class TestPerfumeTag:

    def test_creation(self):
        """Создание тега с полями."""
        tag = PerfumeTag(tag="цитрусовый", confidence=0.95, source="deepseek")

        assert tag.tag == "цитрусовый"
        assert tag.confidence == 0.95
        assert tag.source == "deepseek"

    def test_immutability(self):
        """Frozen dataclass — нельзя изменять."""
        tag = PerfumeTag(tag="свежий")

        with pytest.raises(AttributeError):
            tag.tag = "другой"


class TestSearchFilters:

    def test_empty_filters(self):
        """Пустые фильтры — все поля None."""
        filters = SearchFilters()

        assert filters.genders is None
        assert filters.families is None
        assert filters.brands is None
        assert filters.year_from is None

    def test_to_dict_empty(self):
        """Пустые фильтры → пустой dict."""
        filters = SearchFilters()

        assert filters.to_dict() == {}

    def test_to_dict_partial(self):
        """Частичные фильтры → только непустые поля."""
        filters = SearchFilters(
            genders=("Female", "Unisex"),
            year_from=2010,
        )

        result = filters.to_dict()

        assert result == {
            "genders": ["Female", "Unisex"],
            "year_from": 2010,
        }
        assert "families" not in result
        assert "brands" not in result

    def test_from_lists(self):
        """from_lists() конвертирует списки в tuple."""
        filters = SearchFilters.from_lists(
            genders=["Female"],
            families=["Floral", "Woody"],
            notes=["Бергамот"],
        )

        assert filters.genders == ("Female",)
        assert filters.families == ("Floral", "Woody")
        assert filters.notes == ("Бергамот",)
        assert filters.brands is None

    def test_from_lists_empty_lists_become_none(self):
        """from_lists() с пустыми списками → None."""
        filters = SearchFilters.from_lists(
            genders=[],
            families=None,
        )

        # Пустой список → tuple() что falsy → None в from_lists
        assert filters.families is None

    def test_immutability(self):
        """Frozen dataclass — нельзя изменять."""
        filters = SearchFilters(genders=("Female",))

        with pytest.raises(AttributeError):
            filters.genders = ("Male",)

    def test_to_dict_full(self):
        """Полные фильтры → все поля в dict."""
        filters = SearchFilters(
            genders=("Female",),
            families=("Floral",),
            product_types=("EDP",),
            brands=("Chanel",),
            notes=("Роза",),
            year_from=2000,
            year_to=2024,
        )

        result = filters.to_dict()

        assert len(result) == 7
        assert result["genders"] == ["Female"]
        assert result["year_from"] == 2000
        assert result["year_to"] == 2024
