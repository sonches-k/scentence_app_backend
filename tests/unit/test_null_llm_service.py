import pytest

from app.core.value_objects.perfume import NotePyramid
from app.infrastructure.external.null_llm_service import NullLLMService


pytestmark = pytest.mark.unit


class TestNullLLMService:

    def test_returns_unavailable_message(self):
        service = NullLLMService()
        explanation, _ = service.generate_search_result(query="тест", perfumes=[])
        assert explanation == "Объяснение недоступно"

    def test_returns_empty_pyramid(self):
        service = NullLLMService()
        _, pyramid = service.generate_search_result(query="тест", perfumes=[])
        assert isinstance(pyramid, NotePyramid)
        assert pyramid.top == ()
        assert pyramid.middle == ()
        assert pyramid.base == ()

    def test_ignores_query_and_perfumes(self):
        service = NullLLMService()
        perfumes = [{"name": "Chanel No. 5", "brand": "Chanel"}]
        explanation, pyramid = service.generate_search_result(
            query="тёплый аромат", perfumes=perfumes
        )
        assert explanation == "Объяснение недоступно"
        assert pyramid == NotePyramid()
