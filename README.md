# Scentence — Semantic Perfume Search API

REST API для семантического поиска парфюмерии на основе RAG (Retrieval-Augmented Generation). Принимает текстовый запрос на естественном языке, ищет подходящие ароматы через векторное сходство (pgvector) и возвращает результаты с пирамидой нот и объяснением подбора, сгенерированными через LLM.

![Python](https://img.shields.io/badge/Python-3.11-3776ab?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-336791?logo=postgresql&logoColor=white)

---

## Содержание

- [Концепция](#концепция)
- [Архитектура](#архитектура)
- [Технологический стек](#технологический-стек)
- [API](#api)
- [База данных](#база-данных)
- [Быстрый старт — Docker](#быстрый-старт--docker)
- [Локальная установка](#локальная-установка)
- [Пайплайн данных](#пайплайн-данных)
- [Тестирование](#тестирование)
- [Структура проекта](#структура-проекта)
- [Переменные окружения](#переменные-окружения)

---

## Концепция

Обычный поиск ищет совпадения по словам. Scentence понимает **смысл**:

| Запрос | Обычный поиск | Scentence |
|---|---|---|
| «свежий морской аромат» | ищет слово «морской» | находит «акватические», «озоновые», «водяные» |
| «для первого свидания» | ничего | романтичные, флоральные, лёгкие |
| «как дождь в лесу» | ничего | зелёные, земляные, шипровые |

**Как это работает:**

```
Текст аромата (название + ноты + описание)
        ↓ sentence-transformers (rubert-tiny2)
    Вектор 312 чисел
        ↓ сохраняется в PostgreSQL + pgvector

Запрос пользователя
        ↓ та же модель
    Вектор запроса
        ↓ косинусное сходство (HNSW индекс)
    Топ-N ароматов
        ↓ DeepSeek API
    Пирамида нот + объяснение
```

---

## Архитектура

Проект построен по принципу **Clean Architecture** — три слоя с односторонними зависимостями:

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation (app/api/)                  │
│  routes/ ──► schemas/                                       │
│     │                                                       │
│     └──► dependencies.py ◄── use_cases                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ depends on interfaces only
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Application (app/core/)                   │
│  use_cases/ ──► interfaces/ ◄── entities/                   │
│                      │                                      │
│                      └──► value_objects/                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ implements
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Infrastructure (app/infrastructure/)           │
│  database/repositories.py ──► database/models.py           │
│  external/embedding_service.py                              │
│  external/openai_service.py (DeepSeek + Mock)               │
└─────────────────────────────────────────────────────────────┘
```

| Слой | Путь | Содержит |
|---|---|---|
| **API** | `app/api/` | FastAPI роуты, Pydantic-схемы, DI-контейнер |
| **Domain** | `app/core/` | Use cases, сущности, интерфейсы, value objects |
| **Infrastructure** | `app/infrastructure/` | SQLAlchemy ORM, embedding/LLM сервисы, JWT, email |

**Ключевые паттерны:**

- **Repository Pattern** — `IPerfumeRepository`, `IUserRepository` скрывают SQL от use cases
- **Dependency Injection** — `app/api/dependencies.py` связывает интерфейсы с реализациями
- **Use Case Pattern** — каждый сценарий изолирован в отдельном классе (`SemanticSearchUseCase`, `AddFavoriteUseCase` и др.)
- **DTO** — Pydantic-схемы API не смешиваются с доменными сущностями

---

## Технологический стек

| Компонент | Технология |
|---|---|
| Web framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 (async-совместимый) |
| База данных | PostgreSQL 16 + pgvector 0.7+ |
| Embeddings | `sentence-transformers` — `cointegrated/rubert-tiny2` (312 dim, локально) |
| LLM | DeepSeek API (`deepseek-chat`) — генерация пирамиды нот и объяснений |
| Аутентификация | JWT (python-jose), беспарольная через 6-значный email-код |
| Тесты | pytest + httpx TestClient |
| Контейнеризация | Docker + docker compose |

---

## API

Базовый URL: `http://localhost:8000`  
Swagger UI: [`http://localhost:8000/docs`](http://localhost:8000/docs)

### Поиск

| Метод | Эндпоинт | Описание | Auth |
|---|---|---|---|
| `POST` | `/api/v1/search/` | Семантический поиск по свободному тексту | опционально |
| `POST` | `/api/v1/search/similar/{id}` | Найти похожие ароматы по ID | — |

```bash
# Семантический поиск
curl -X POST http://localhost:8000/api/v1/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "тёплый восточный аромат с ванилью и деревом", "limit": 3}'
```

```json
{
  "query": "тёплый восточный аромат с ванилью и деревом",
  "note_pyramid": {
    "top": ["Бергамот", "Кардамон"],
    "middle": ["Уд", "Амбра", "Роза"],
    "base": ["Сандал", "Ваниль", "Мускус"]
  },
  "explanation": "Эти ароматы строятся на тёплой базе сандала и ванили...",
  "perfumes": [...],
  "total_found": 3
}
```

### Каталог

| Метод | Эндпоинт | Описание |
|---|---|---|
| `GET` | `/api/v1/perfumes/{id}` | Карточка аромата |
| `GET` | `/api/v1/perfumes/filters/all` | Все доступные фильтры (пол, семейство, ноты, бренды) |
| `GET` | `/api/v1/perfumes/brands/all` | Список брендов |

### Аутентификация (беспарольная)

| Метод | Эндпоинт | Описание |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Запросить код верификации на email |
| `POST` | `/api/v1/auth/verify` | Подтвердить код → получить JWT токен |
| `POST` | `/api/v1/auth/login` | Войти в существующий аккаунт |

### Пользователь (требует Bearer токен)

| Метод | Эндпоинт | Описание |
|---|---|---|
| `GET` / `PUT` | `/api/v1/users/profile` | Профиль пользователя |
| `GET` | `/api/v1/users/favorites` | Список избранных ароматов |
| `POST` | `/api/v1/users/favorites/{id}` | Добавить в избранное |
| `DELETE` | `/api/v1/users/favorites/{id}` | Удалить из избранного |
| `GET` | `/api/v1/users/history` | История поиска |

### Прочее

| Метод | Эндпоинт | Описание |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI |

---

## База данных

Схема из 8 таблиц + расширение pgvector:

```mermaid
erDiagram
    perfumes {
        int id PK
        varchar name
        varchar brand
        int year
        varchar product_type
        varchar family
        varchar gender
        text description
        varchar image_url
        float price
    }
    notes {
        int id PK
        varchar name UK
        varchar category
    }
    perfume_notes {
        int perfume_id FK
        int note_id FK
        varchar level
    }
    perfume_embeddings {
        int perfume_id FK,UK
        vector embedding
    }
    perfume_tags {
        int perfume_id FK
        varchar tag
        float confidence
        varchar source
    }
    users {
        int id PK
        varchar email UK
        varchar name
    }
    user_favorites {
        int user_id FK
        int perfume_id FK
    }
    search_history {
        int user_id FK
        text query_text
        jsonb filters
    }

    perfumes ||--o{ perfume_notes : ""
    notes ||--o{ perfume_notes : ""
    perfumes ||--o| perfume_embeddings : ""
    perfumes ||--o{ perfume_tags : ""
    users ||--o{ user_favorites : ""
    perfumes ||--o{ user_favorites : ""
    users ||--o{ search_history : ""
```

**Ключевые особенности схемы:**

- `perfume_embeddings.embedding` — тип `VECTOR(312)` из pgvector
- HNSW-индекс на `embedding` — быстрый поиск ближайших соседей O(log N)
- `perfume_tags.source` — различает теги из парсинга (`parsed`) и от LLM (`deepseek`)
- `search_history.filters` — `jsonb`, сохраняет произвольные фильтры поиска

---

## Быстрый старт — Docker

**Требования:** Docker Desktop, docker compose v2+

```bash
# 1. Клонировать репозиторий
git clone https://github.com/sonches-k/scentence_app_backend.git
cd scentence_app_backend

# 2. Настроить окружение
cp .env.example .env
# Обязательно задать: JWT_SECRET, DEEPSEEK_API_KEY (или оставить пустым — Mock-режим)
# Для Docker: DATABASE_URL=postgresql://postgres:password@postgres:5432/perfume_db

# 3. Собрать образы (первый раз ~10-15 мин из-за torch)
docker compose build

# 4. Запустить базу данных
docker compose up -d postgres

# 5. Инициализировать БД + загрузить данные
docker compose run --rm init

# 6. Сгенерировать эмбеддинги
docker compose run --rm app python scripts/generate_embeddings.py

# 7. Запустить приложение
docker compose up -d app
```

Проверить запуск:

```bash
curl http://localhost:8000/health
# {"status":"healthy"}

curl -X POST http://localhost:8000/api/v1/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "свежий цветочный аромат для лета", "limit": 3}'
```

---

## Локальная установка

### Требования

| Программа | Версия |
|---|---|
| Python | 3.11+ |
| PostgreSQL | 16+ |
| pgvector | 0.7+ |

### Установка

```bash
# 1. Клонировать и создать виртуальное окружение
git clone https://github.com/sonches-k/scentence_app_backend.git
cd scentence_app_backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Установить зависимости
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 3. Настроить .env
cp .env.example .env
# DATABASE_URL=postgresql://postgres:<пароль>@localhost:5432/perfume_db
# JWT_SECRET=<ваш-секрет>

# 4. Создать БД и схему
psql -U postgres -c "CREATE DATABASE perfume_db;"
python scripts/init_db.py

# 5. Загрузить данные (нужен perfumes.json)
python scripts/load_to_db.py --input perfumes.json --clear

# 6. Сгенерировать эмбеддинги
python scripts/generate_embeddings.py

# 7. Запустить сервер
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> **Альтернатива для PostgreSQL без pgvector:** запустить только БД через Docker:
> ```bash
> docker run -d --name pgvector-db \
>   -e POSTGRES_PASSWORD=password \
>   -e POSTGRES_DB=perfume_db \
>   -p 5432:5432 \
>   pgvector/pgvector:pg16
> ```

---

## Пайплайн данных

Данные о ароматах собираются парсерами, обогащаются эмбеддингами и LLM-тегами:

```
духи.рф + randewoo.ru
      ↓ парсеры (Selenium + requests)
  perfumes.json
      ↓ scripts/load_to_db.py
  PostgreSQL (perfumes, notes, perfume_notes)
      ↓ scripts/generate_embeddings.py
  perfume_embeddings (VECTOR(312))
      ↓ scripts/generate_tags.py  [опционально, нужен DEEPSEEK_API_KEY]
  perfume_tags (source='deepseek')
```

### Скрипты пайплайна

| Скрипт | Назначение |
|---|---|
| `scripts/init_db.py` | Создать pgvector-расширение, таблицы и HNSW-индекс |
| `scripts/load_to_db.py` | Загрузить `perfumes.json` в БД |
| `scripts/generate_embeddings.py` | Сгенерировать 312-dim векторы для всех ароматов |
| `scripts/generate_tags.py` | Сгенерировать семантические теги через DeepSeek API |

```bash
# Загрузка с нуля
python scripts/init_db.py
python scripts/load_to_db.py --input perfumes.json --clear
python scripts/generate_embeddings.py

# Теги (требует DEEPSEEK_API_KEY)
python scripts/generate_tags.py --limit 5 --dry-run  # тест
python scripts/generate_tags.py                       # все ароматы
```

> Пример данных в формате JSON: [`data/examples/sample_perfumes.json`](data/examples/sample_perfumes.json)

---

## Тестирование

Тесты организованы в три уровня:

```
tests/
├── conftest.py                   # fixtures: mock-репозитории, TestClient
├── unit/                         # Use cases и value objects (без БД, всё замокано)
│   ├── test_search_use_case.py
│   ├── test_perfume_use_case.py
│   ├── test_user_use_case.py
│   └── test_value_objects.py
├── integration/                  # FastAPI TestClient с переопределёнными DI
│   ├── test_api_search.py
│   ├── test_api_perfumes.py
│   └── test_user_api.py
└── e2e/                          # Полные тесты против реальной БД
    ├── test_api_e2e.py
    ├── test_repositories.py
    └── test_use_cases.py
```

```bash
# Все тесты
pytest

# Только unit (быстро, без БД)
pytest tests/unit/ -v

# С отчётом о покрытии
pytest tests/unit/ tests/integration/ --cov=app --cov-report=term-missing

# E2E (требует запущенной PostgreSQL)
pytest tests/e2e/ -v
```

---

## Структура проекта

```
scentence_app_backend/
├── app/
│   ├── main.py                      # Точка входа FastAPI
│   ├── api/
│   │   ├── dependencies.py          # DI-контейнер
│   │   ├── routes/
│   │   │   ├── auth.py              # /auth/*
│   │   │   ├── perfumes.py          # /perfumes/*
│   │   │   ├── search.py            # /search/*
│   │   │   └── users.py             # /users/*
│   │   └── schemas/
│   │       ├── auth.py
│   │       ├── perfume.py           # 12 Pydantic-классов
│   │       └── search.py
│   ├── core/
│   │   ├── entities/
│   │   │   ├── perfume.py           # Perfume, PerfumeNote, Note, PerfumeWithRelevance
│   │   │   └── user.py              # User, UserFavorite, SearchHistoryEntry
│   │   ├── interfaces/
│   │   │   ├── repositories.py      # IPerfumeRepository, IUserRepository (ABC)
│   │   │   └── services.py          # IEmbeddingService, ILLMService (ABC)
│   │   ├── use_cases/
│   │   │   ├── auth.py
│   │   │   ├── perfume.py           # GetPerfume, GetFilters, GetBrands
│   │   │   ├── search.py            # SemanticSearch, FindSimilar
│   │   │   └── user.py              # Favorites, SearchHistory
│   │   ├── value_objects/
│   │   │   ├── perfume.py           # NotePyramid, PerfumeTag
│   │   │   └── search.py            # SearchFilters
│   │   └── exceptions.py
│   └── infrastructure/
│       ├── config.py                # Pydantic Settings (читает .env)
│       ├── database/
│       │   ├── connection.py        # SQLAlchemy engine, SessionLocal
│       │   ├── models.py            # 8 ORM-моделей
│       │   └── repositories.py      # SQLAlchemyPerfumeRepository, SQLAlchemyUserRepository
│       ├── external/
│       │   ├── embedding_service.py # SentenceTransformerEmbeddingService
│       │   ├── openai_service.py    # OpenAI / DeepSeek / Mock LLM сервисы
│       │   └── prompts.py           # LLM prompt templates
│       ├── security/
│       │   └── jwt_handler.py
│       └── services/
│           └── email_service.py     # Console (dev) или SMTP
├── scripts/
│   ├── init_db.py
│   ├── load_to_db.py
│   ├── generate_embeddings.py
│   └── generate_tags.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── data/
│   └── examples/
│       └── sample_perfumes.json     # Пример данных (3-5 ароматов)
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

---

## Переменные окружения

| Переменная | Обязательная | Описание | Дефолт |
|---|---|---|---|
| `DATABASE_URL` | ✅ | Строка подключения к PostgreSQL | `postgresql://postgres:password@localhost:5432/perfume_db` |
| `POSTGRES_PASSWORD` | ✅ | Пароль PostgreSQL (для Docker Compose) | `password` |
| `JWT_SECRET` | ✅ | Секрет для подписи JWT токенов | слабый дефолт |
| `DEEPSEEK_API_KEY` | ❌ | API ключ DeepSeek — без него Mock-режим | пустой |
| `OPENAI_API_KEY` | ❌ | API ключ OpenAI (приоритет выше DeepSeek) | пустой |
| `EMAIL_BACKEND` | ❌ | `console` (лог в терминал) или `smtp` | `console` |
| `EMBEDDING_DIMENSION` | ❌ | Размерность векторов (312 для rubert-tiny2) | `312` |
| `JWT_EXPIRE_DAYS` | ❌ | Срок жизни JWT в днях | `7` |
| `DEBUG` | ❌ | Включить SQL-логи SQLAlchemy | `false` |

Полный список с описаниями — в [`.env.example`](.env.example).

> **Важно:** при смене `JWT_SECRET` все выданные токены становятся невалидными.

---

## Mock-режим (без API ключей)

Если `DEEPSEEK_API_KEY` не задан, приложение автоматически использует `MockLLMService`:
- поиск работает полностью (векторный поиск через pgvector)
- пирамида нот и объяснение — захардкоженная заглушка
- все эндпоинты доступны

```
INFO: LLM: используется MockLLMService (ключ не задан)
```

---

## Типичные ошибки

| Ошибка | Решение |
|---|---|
| `extension "vector" is not available` | pgvector не установлен — использовать Docker для БД: `pgvector/pgvector:pg16` |
| `could not connect to server` | PostgreSQL не запущен или неверный пароль в `DATABASE_URL` |
| `table verification_codes does not exist` | Переинициализировать БД: `python scripts/init_db.py` |
| `No perfumes found` в поиске | Нет эмбеддингов — запустить `python scripts/generate_embeddings.py` |
| `401 Unauthorized` на `/users/*` | Отсутствует или истёк JWT токен |
| `LLM: MockLLMService` | Нормально — добавить `DEEPSEEK_API_KEY` для полноценного режима |

---

