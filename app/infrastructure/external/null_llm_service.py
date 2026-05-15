from app.core.entities import NotePyramid
from app.core.interfaces import ILLMService

_UNAVAILABLE_MESSAGE = "Объяснение недоступно"


class NullLLMService(ILLMService):
    """Null-object реализация ILLMService для случая, когда LLM не сконфигурирован."""

    def generate_search_result(self, query: str, perfumes: list[dict]) -> tuple[str, NotePyramid]:
        return _UNAVAILABLE_MESSAGE, NotePyramid()
