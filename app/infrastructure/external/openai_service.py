"""
Реализация сервисов на базе OpenAI API.
"""

import json
from typing import Optional

from app.core.entities import NotePyramid
from app.core.interfaces import IEmbeddingService, ILLMService
from app.infrastructure.config import settings
from app.infrastructure.external.prompts import (
    EXPLANATION_SYSTEM_PROMPT,
    build_explanation_prompt,
)


class OpenAIEmbeddingService(IEmbeddingService):
    """OpenAI реализация сервиса эмбеддингов."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._model = settings.EMBEDDING_MODEL
        self._client = None

    def _get_client(self):
        """Lazy initialization клиента OpenAI."""
        if self._client is None:
            if not self._api_key:
                raise ValueError("OPENAI_API_KEY is not configured")
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def generate_embedding(self, text: str) -> list[float]:
        """Сгенерировать эмбеддинг для текста."""
        client = self._get_client()
        response = client.embeddings.create(
            model=self._model,
            input=text,
        )
        return response.data[0].embedding

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Сгенерировать эмбеддинги для списка текстов."""
        client = self._get_client()
        response = client.embeddings.create(
            model=self._model,
            input=texts,
        )
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]


class OpenAILLMService(ILLMService):
    """OpenAI реализация сервиса LLM."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._model = settings.LLM_MODEL
        self._client = None

    def _get_client(self):
        """Lazy initialization клиента OpenAI."""
        if self._client is None:
            if not self._api_key:
                raise ValueError("OPENAI_API_KEY is not configured")
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def generate_search_explanation(
        self,
        query: str,
        perfumes: list[dict],
    ) -> str:
        """Сгенерировать пояснение к результатам поиска."""
        if not perfumes:
            return "К сожалению, не удалось найти ароматы, соответствующие вашему запросу."

        prompt = build_explanation_prompt(query, perfumes)
        client = self._get_client()
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": EXPLANATION_SYSTEM_PROMPT,
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.7,
        )

        return response.choices[0].message.content.strip()

    def extract_note_pyramid(self, query: str) -> NotePyramid:
        """Извлечь пирамиду нот из запроса пользователя."""
        prompt = f"""Проанализируй запрос пользователя на поиск аромата и определи,
какие парфюмерные ноты могли бы соответствовать этому описанию.

Запрос: "{query}"

Верни JSON в формате:
{{
    "top": ["нота1", "нота2"],
    "middle": ["нота1", "нота2"],
    "base": ["нота1", "нота2"]
}}

Используй реальные парфюмерные ноты. Если в запросе упоминаются конкретные ноты,
включи их. Если нет - предложи подходящие на основе описания атмосферы/настроения.
Верни ТОЛЬКО JSON без дополнительного текста."""

        client = self._get_client()
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": "Ты эксперт по парфюмерии. Возвращаешь только JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=200,
            temperature=0.5,
        )

        try:
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content)
            return NotePyramid(
                top=data.get("top", []),
                middle=data.get("middle", []),
                base=data.get("base", []),
            )
        except (json.JSONDecodeError, KeyError):
            return NotePyramid()
