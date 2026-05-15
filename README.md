# Scentence — Semantic Perfume Search API

REST API для приложения подбора парфюмерии. Принимает текстовый запрос на естественном языке, ищет ароматы через векторное сходство (pgvector) и возвращает результаты с пирамидой нот и объяснением от LLM.

![Python](https://img.shields.io/badge/Python-3.11-3776ab?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-336791?logo=postgresql&logoColor=white)

**Стек:** FastAPI · SQLAlchemy 2.0 · PostgreSQL 16 + pgvector · sentence-transformers (multilingual-e5-large, 1024 dim) · DeepSeek API · Redis · JWT (беспарольная аутентификация)

---

## Быстрый старт — Docker

```bash
# 1. Настроить окружение
cp .env.example .env
# Задать JWT_SECRET и DEEPSEEK_API_KEY (без ключа LLM — ответ без объяснения)

# 2. Запустить БД
docker compose up -d postgres

# 3. Инициализировать схему и загрузить данные
docker compose --profile init run --rm init

# 4. Сгенерировать эмбеддинги (первый раз ~20 мин — скачивается модель)
docker compose run --rm app python scripts/generate_embeddings.py

# 5. Запустить приложение
docker compose up -d app
```

Проверка:

```bash
curl http://localhost:8000/health
# {"status":"healthy","db":"ok","redis":"ok"}
```

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Локальная установка

```bash
python -m venv venv && source venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

cp .env.example .env
# DATABASE_URL=postgresql://postgres:<пароль>@localhost:5432/perfume_db

python scripts/init_db.py
python scripts/load_to_db.py --input perfumes.json --clear
python scripts/generate_embeddings.py

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> Для PostgreSQL + pgvector без локальной установки:
> `docker run -d -e POSTGRES_PASSWORD=password -e POSTGRES_DB=perfume_db -p 5432:5432 pgvector/pgvector:pg16`

---

## API

| Метод | Эндпоинт | Описание | Auth |
|---|---|---|---|
| `POST` | `/api/v1/search/` | Семантический поиск | опц. |
| `POST` | `/api/v1/search/similar/{id}` | Похожие ароматы | — |
| `GET` | `/api/v1/perfumes/{id}` | Карточка аромата | — |
| `GET` | `/api/v1/perfumes/filters` | Фильтры (пол, семейство, категория) | — |
| `GET` | `/api/v1/perfumes/brands/suggest` | Подсказки брендов | — |
| `GET` | `/api/v1/perfumes/notes/suggest` | Подсказки нот | — |
| `POST` | `/api/v1/auth/register` | Запросить код на email | — |
| `POST` | `/api/v1/auth/login` | Войти (повторный код) | — |
| `POST` | `/api/v1/auth/verify` | Подтвердить код → access + refresh | — |
| `POST` | `/api/v1/auth/refresh` | Обновить access-токен | — |
| `POST` | `/api/v1/auth/logout` | Выйти (инвалидировать refresh) | — |
| `GET/PUT` | `/api/v1/users/profile` | Профиль пользователя | ✅ |
| `GET/POST/DELETE` | `/api/v1/users/favorites/{id}` | Избранное | ✅ |
| `GET/DELETE` | `/api/v1/users/history` | История поиска | ✅ |
| `DELETE` | `/api/v1/users/history/{entry_id}` | Удалить запись из истории | ✅ |

---

## Переменные окружения

| Переменная | Обязательная | Описание |
|---|---|---|
| `DATABASE_URL` | ✅ | Строка подключения к PostgreSQL |
| `JWT_SECRET` | ✅ | Секрет для подписи токенов |
| `DEEPSEEK_API_KEY` | ❌ | Без него LLM-объяснение не генерируется |
| `REDIS_URL` | ❌ | Кэширование фильтров и поиска |
| `EMAIL_BACKEND` | ❌ | `console` (лог) или `smtp` (дефолт: `console`) |
| `DEBUG` | ❌ | SQL-логи SQLAlchemy |

Полный список — в [`.env.example`](.env.example).

---

## Тесты

```bash
pytest tests/unit/ -v                         # без БД
pytest tests/unit/ tests/integration/ -v      # с TestClient
pytest tests/e2e/ -v                          # требует PostgreSQL
```

---

## Типичные ошибки

| Ошибка | Решение |
|---|---|
| `extension "vector" is not available` | Использовать Docker-образ `pgvector/pgvector:pg16` |
| `table verification_codes does not exist` | `python scripts/init_db.py` |
| `No perfumes found` в поиске | Запустить `python scripts/generate_embeddings.py` |
| `401 Unauthorized` | Отсутствует или истёк JWT токен |
