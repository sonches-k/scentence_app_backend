"""
Нагрузочное тестирование Scentence backend.

Сценарии
────────
UnCachedSearchUser  (вес 5) — анонимный пользователь, уникальные запросы.
  Каждый запрос гарантированно минует Redis-кэш (к запросу добавляется
  случайный суффикс). Тестирует полный pipeline:
    embedding (локальная ML-модель) → pgvector HNSW → DeepSeek LLM.
  Именно здесь проверяется требование ТЗ 4.1.5.3: p95 ≤ 10 сек.

CachedSearchUser    (вес 2) — анонимный пользователь, повторяющиеся запросы.
  Использует фиксированный набор из 10 популярных запросов — при втором
  и последующих обращениях они уже закэшированы в Redis.
  Ожидаемая латентность: 5–50 мс (на порядки меньше незакэшированного).

AuthenticatedBrowseUser (вес 3) — авторизованный пользователь.
  Просматривает карточки ароматов, похожие, избранное, историю поиска.
  Требует предварительной подготовки токенов:
    python scripts/create_load_test_users.py

Подготовка
──────────
1. Запустить backend:      docker-compose up -d
2. Создать тест-пользователей (один раз):
     python scripts/create_load_test_users.py
3. Установить locust:      pip install locust

Запуск (интерактивный веб-UI, http://localhost:8089)
────────────────────────────────────────────────────
  locust -f scripts/locustfile.py --host http://localhost:8000

Запуск headless (ПМИ — 10 пользователей, 5 минут)
──────────────────────────────────────────────────
  locust -f scripts/locustfile.py \
         --host http://localhost:8000 \
         --users 10 --spawn-rate 2 --run-time 5m --headless \
         --html load_test_results/report_$(date +%Y%m%d_%H%M%S).html

Анализ component-timings из логов сервера (во время теста)
──────────────────────────────────────────────────────────
  docker logs <container> 2>&1 | grep search_timing
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

from locust import HttpUser, between, task

# ── Данные для тестов ─────────────────────────────────────────────────────────

# Большой набор уникальных поисковых запросов — для UnCachedSearchUser.
UNIQUE_QUERIES: list[str] = [
    "лёгкий летний цветочный аромат",
    "тёплый сладкий ванильный для зимних вечеров",
    "офисный сдержанный мужской парфюм",
    "восточный пряный аромат для свиданий",
    "свежий цитрусовый на каждый день",
    "древесный дымный аромат с кожей",
    "морской аромат с нотами соли и водорослей",
    "сладкая гурманская парфюмерия с шоколадом",
    "роза и пачули вечерний женский",
    "зелёный травяной аромат как после дождя",
    "пудровый мускусный нежный женский",
    "озоновый прохладный для жаркого дня",
    "фруктовый ягодный молодёжный",
    "анималистичный мускусный соблазнительный",
    "дымный благовонный церковный аромат",
    "ладан и амбра медитативный",
    "масляная роза с ноткой меда",
    "цитрусовый зелёный для спорта и активного дня",
    "ванильный кофейный гурман",
    "ирис и фиалка элегантный",
    "пачули старая школа классика",
    "морозный мятный ментоловый освежающий",
    "сандал и ваниль уютный домашний",
    "горький миндаль вишнёвый тёмный",
    "табачный кожаный мужской вечерний",
    "лаванда и розмарин фужерный классический",
    "белые цветы свадебный нежный",
    "грейпфрут и базилик утренний бодрящий",
    "пачули и амбра тёплый чувственный",
    "морской бриз и кокос отпускной",
    "пион и магнолия весенний свежий",
    "уд и шафран дорогой восточный",
    "имбирь и кардамон пряный согревающий",
    "берёзовый дёготь можжевельник суровый",
    "крем-брюле и карамель сладкий десертный",
    "белый чай и бергамот лёгкий деловой",
    "малина и пион ягодный женский",
    "ветивер и бобы тонка тёмный загадочный",
    "огурец и арбуз летний свежий",
    "нероли и петитгрейн солнечный аромат",
    "табак и виски прокуренный бар",
    "можжевельник и сосна горный лес",
    "карамель и попкорн уютный детский",
    "мирра и ладан загадочный мистический",
    "шипровый аромат с дубовым мхом ретро",
    "молочный лактонный мягкий аромат",
    "перец и куркума пряный гастрономический",
    "сирень и ландыш весенний романтичный",
    "лавр и тимьян средиземноморский",
    "кокос и тиаре тропический пляжный",
]

# Фиксированные запросы для теста кэша — те же самые строки, без суффиксов.
CACHED_QUERIES: list[str] = UNIQUE_QUERIES[:10]


# ── Загрузка тестовых данных ──────────────────────────────────────────────────

_tokens_path = Path(__file__).parent / "load_test_tokens.json"
_test_data: dict = {}

if _tokens_path.exists():
    try:
        _test_data = json.loads(_tokens_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[locustfile] Не удалось загрузить {_tokens_path}: {exc}")

_all_tokens: list[dict] = _test_data.get("tokens", [])
_perfume_ids: list[int] = _test_data.get("perfume_ids", list(range(1, 51)))

if not _all_tokens:
    print(
        "[locustfile] ВНИМАНИЕ: файл load_test_tokens.json не найден или пуст.\n"
        "             Запустите: python scripts/create_load_test_users.py\n"
        "             AuthenticatedBrowseUser будет работать без авторизации."
    )

if not _perfume_ids:
    _perfume_ids = list(range(1, 51))


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _random_perfume_id() -> int:
    return random.choice(_perfume_ids)


def _random_token() -> Optional[dict]:
    return random.choice(_all_tokens) if _all_tokens else None


# ── Пользовательские сценарии ─────────────────────────────────────────────────

class UnCachedSearchUser(HttpUser):
    """
    Анонимный пользователь, выполняющий уникальные поисковые запросы.

    Каждый запрос содержит случайный числовой суффикс, поэтому Redis-кэш
    никогда не срабатывает. Тестирует полный pipeline:
    embedding → pgvector → LLM.

    Требование ТЗ 4.1.5.3 (p95 ≤ 10 сек) проверяется именно здесь.
    """

    weight = 5
    wait_time = between(5, 20)

    @task(3)
    def search_uncached(self) -> None:
        base_query = random.choice(UNIQUE_QUERIES)
        # Суффикс гарантирует уникальность и обход кэша
        query = f"{base_query} {random.randint(10000, 99999)}"
        with self.client.post(
            "/api/v1/search/",
            json={"query": query, "limit": 5},
            catch_response=True,
            name="POST /search [uncached]",
        ) as resp:
            if resp.status_code == 504:
                resp.failure("LLM timeout (504)")
            elif resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")

    @task(1)
    def get_perfume_detail(self) -> None:
        perfume_id = _random_perfume_id()
        self.client.get(
            f"/api/v1/perfumes/{perfume_id}",
            name="GET /perfumes/{id}",
        )


class CachedSearchUser(HttpUser):
    """
    Анонимный пользователь, повторяющий один из 10 популярных запросов.

    После первого прохода результаты закэшированы в Redis (TTL = 180 дней).
    Тестирует производительность Redis-слоя изолированно от ML и LLM.
    """

    weight = 2
    wait_time = between(1, 5)

    @task
    def search_cached(self) -> None:
        query = random.choice(CACHED_QUERIES)
        with self.client.post(
            "/api/v1/search/",
            json={"query": query, "limit": 5},
            catch_response=True,
            name="POST /search [cached]",
        ) as resp:
            if resp.status_code not in (200,):
                resp.failure(f"HTTP {resp.status_code}")


class AuthenticatedBrowseUser(HttpUser):
    """
    Авторизованный пользователь.

    Просматривает карточки ароматов, похожие ароматы, управляет избранным
    и историей поиска. Токены берутся из load_test_tokens.json.

    Тестирует требования ТЗ 4.1.5.1 (login p95 ≤ 2 с),
    4.1.5.4 (perfumes/{id} p95 ≤ 1 с), 4.1.5.5 (favorites p95 ≤ 1 с).
    """

    weight = 3
    wait_time = between(2, 8)

    def on_start(self) -> None:
        token_data = _random_token()
        if token_data:
            self._auth_headers = {
                "Authorization": f"Bearer {token_data['access_token']}"
            }
            self._refresh_token = token_data.get("refresh_token", "")
        else:
            self._auth_headers = {}
            self._refresh_token = ""

    @task(3)
    def get_perfume_detail(self) -> None:
        perfume_id = _random_perfume_id()
        self.client.get(
            f"/api/v1/perfumes/{perfume_id}",
            name="GET /perfumes/{id}",
        )

    @task(2)
    def get_similar(self) -> None:
        perfume_id = _random_perfume_id()
        with self.client.post(
            f"/api/v1/search/similar/{perfume_id}",
            catch_response=True,
            name="POST /search/similar/{id}",
        ) as resp:
            if resp.status_code == 404:
                resp.success()  # несуществующий ID — ожидаемое поведение
            elif resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")

    @task(2)
    def get_favorites(self) -> None:
        self.client.get(
            "/api/v1/users/favorites",
            headers=self._auth_headers,
            name="GET /users/favorites",
        )

    @task(1)
    def add_favorite(self) -> None:
        perfume_id = _random_perfume_id()
        with self.client.post(
            f"/api/v1/users/favorites/{perfume_id}",
            headers=self._auth_headers,
            catch_response=True,
            name="POST /users/favorites/{id}",
        ) as resp:
            # 201 Created или 200 OK (идемпотентность) — оба успешны
            if resp.status_code not in (200, 201):
                resp.failure(f"HTTP {resp.status_code}")
            else:
                resp.success()

    @task(1)
    def remove_favorite(self) -> None:
        perfume_id = _random_perfume_id()
        with self.client.delete(
            f"/api/v1/users/favorites/{perfume_id}",
            headers=self._auth_headers,
            catch_response=True,
            name="DELETE /users/favorites/{id}",
        ) as resp:
            # 404 — не было в избранном, это нормально
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(1)
    def get_history(self) -> None:
        self.client.get(
            "/api/v1/users/history",
            headers=self._auth_headers,
            name="GET /users/history",
        )

    @task(2)
    def search_authenticated(self) -> None:
        """Поиск с токеном — запрос сохраняется в историю пользователя."""
        query = random.choice(UNIQUE_QUERIES)
        with self.client.post(
            "/api/v1/search/",
            json={"query": query, "limit": 5},
            headers=self._auth_headers,
            catch_response=True,
            name="POST /search [auth]",
        ) as resp:
            if resp.status_code == 504:
                resp.failure("LLM timeout (504)")
            elif resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")

    @task(1)
    def get_profile(self) -> None:
        self.client.get(
            "/api/v1/users/profile",
            headers=self._auth_headers,
            name="GET /users/profile",
        )
