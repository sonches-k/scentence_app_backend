import json
from typing import Optional

from app.core.entities import NotePyramid
from app.core.exceptions import LLMTimeoutError
from app.core.interfaces import ILLMService
from app.infrastructure.config import settings
from app.infrastructure.external.prompts import (
    SEARCH_RESULT_SYSTEM_PROMPT,
    build_search_result_prompt,
)


_LLM_REQUEST_TIMEOUT = 60.0


def _parse_llm_json(content: str) -> dict:
    content = content.strip()
    if "```" in content:
        for part in content.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                content = part
                break
    return json.loads(content)


class DeepSeekLLMService(ILLMService):

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.DEEPSEEK_API_KEY
        self._model = settings.DEEPSEEK_MODEL
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self._api_key:
                raise ValueError("DEEPSEEK_API_KEY is not configured")
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self._api_key,
                base_url="https://api.deepseek.com",
                timeout=_LLM_REQUEST_TIMEOUT,
            )
        return self._client

    def generate_search_result(
        self,
        query: str,
        perfumes: list[dict],
    ) -> tuple[str, NotePyramid]:
        if not perfumes:
            return "К сожалению, не удалось найти ароматы, соответствующие вашему запросу.", NotePyramid()

        prompt = build_search_result_prompt(query, perfumes)
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SEARCH_RESULT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
                temperature=0.7,
            )
        except Exception as exc:
            from openai import APITimeoutError

            if isinstance(exc, APITimeoutError):
                raise LLMTimeoutError(
                    f"LLM service timed out after {_LLM_REQUEST_TIMEOUT:.0f}s"
                ) from exc
            return self._fallback_explanation(perfumes)

        try:
            data = _parse_llm_json(response.choices[0].message.content)
            explanation = data.get("explanation", "")
            pyramid_data = data.get("pyramid", {})
            pyramid = NotePyramid(
                top=pyramid_data.get("top", []),
                middle=pyramid_data.get("middle", []),
                base=pyramid_data.get("base", []),
            )
            return explanation, pyramid
        except (json.JSONDecodeError, KeyError, AttributeError, TypeError):
            return self._fallback_explanation(perfumes)

    @staticmethod
    def _fallback_explanation(perfumes: list[dict]) -> tuple[str, NotePyramid]:
        names = ", ".join(p["name"] for p in perfumes[:3])
        return f"По вашему запросу найдены ароматы: {names}.", NotePyramid()
