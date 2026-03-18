"""
Реализация ILLMService на базе DeepSeek API (OpenAI-совместимый).
"""

import json
from typing import Optional

from app.core.entities import NotePyramid
from app.core.interfaces import ILLMService
from app.infrastructure.config import settings
from app.infrastructure.external.prompts import (
    EXPLANATION_SYSTEM_PROMPT,
    build_explanation_prompt,
)


class DeepSeekLLMService(ILLMService):
    """DeepSeek реализация сервиса LLM (OpenAI-совместимый API)."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.DEEPSEEK_API_KEY
        self._model = settings.DEEPSEEK_MODEL
        self._client = None

    def _get_client(self):
        """Lazy initialization клиента."""
        if self._client is None:
            if not self._api_key:
                raise ValueError("DEEPSEEK_API_KEY is not configured")
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self._api_key,
                base_url="https://api.deepseek.com",
            )
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
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=400,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            names = ", ".join(p["name"] for p in perfumes[:3])
            return f"По вашему запросу найдены ароматы: {names}."

    def extract_note_pyramid(self, query: str) -> NotePyramid:
        """Извлечь пирамиду нот из запроса пользователя."""
        prompt = (
            f"Ты — эксперт по парфюмерии. Пользователь описал желаемый аромат: '{query}'. "
            f"Определи парфюмерные ноты, которые соответствуют этому описанию. "
            f'Ответь ТОЛЬКО в формате JSON: {{"top": ["нота1", "нота2"], "heart": ["нота1", "нота2"], "base": ["нота1", "нота2"]}}. '
            f"Выбирай реальные парфюмерные ноты (бергамот, ваниль, сандал, мускус и т.д.). "
            f"По 2-4 ноты на каждый уровень."
        )

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.5,
            )
            content = response.choices[0].message.content.strip()
            if "```" in content:
                parts = content.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("{"):
                        content = part
                        break
            data = json.loads(content)
            return NotePyramid(
                top=data.get("top", []),
                middle=data.get("heart", data.get("middle", [])),
                base=data.get("base", []),
            )
        except Exception:
            return NotePyramid()
