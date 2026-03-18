"""
Скрипт для инициализации базы данных.

Создает все таблицы и индексы.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.database import engine, Base
from app.infrastructure.database.models import (
    PerfumeModel,
    NoteModel,
    PerfumeNoteModel,
    PerfumeEmbeddingModel,
    PerfumeTagModel,
    UserModel,
    UserFavoriteModel,
    SearchHistoryModel,
    VerificationCodeModel,  # ОБЯЗАТЕЛЬНО: иначе таблица verification_codes не создастся
)
from sqlalchemy import text


def create_pgvector_extension():
    """Создать расширение pgvector, если оно еще не создано."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    print("✓ Расширение pgvector создано или уже существует")


def create_tables():
    """Создать все таблицы."""
    Base.metadata.create_all(bind=engine)
    print("✓ Все таблицы созданы")


def create_indexes():
    """Создать индексы для векторного поиска."""
    with engine.connect() as conn:
        # HNSW индекс для быстрого векторного поиска
        # Используем косинусное расстояние (vector_cosine_ops)
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS perfume_embeddings_hnsw_idx
            ON perfume_embeddings
            USING hnsw (embedding vector_cosine_ops)
        """))
        conn.commit()
    print("✓ Индексы для векторного поиска созданы")


def main():
    """Главная функция инициализации."""
    print("Начинаем инициализацию базы данных...")
    print()

    try:
        # 1. Создаем расширение pgvector
        create_pgvector_extension()

        # 2. Создаем все таблицы
        create_tables()

        # 3. Создаем индексы
        create_indexes()

        print()
        print("✅ База данных успешно инициализирована!")
        print()
        print("Следующие шаги:")
        print("1. Загрузите данные: python scripts/load_to_db.py --input perfumes.json")
        print("2. Сгенерируйте embeddings: python scripts/generate_embeddings.py")
        print("3. (Опционально) Теги DeepSeek: python scripts/generate_tags.py")
        print("4. Запустите сервер: uvicorn app.main:app --reload")

    except Exception as e:
        print(f"❌ Ошибка при инициализации базы данных: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
