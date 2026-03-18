"""
Скрипт генерации embeddings для всех ароматов в БД.

Использование:
    python scripts/generate_embeddings.py                    # Генерация для всех
    python scripts/generate_embeddings.py --batch-size 10    # Указать размер батча
    python scripts/generate_embeddings.py --force            # Перегенерировать
"""

import sys
import os
import argparse
import logging
from typing import List

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Добавить путь к app для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.infrastructure.external.embedding_service import SentenceTransformerEmbeddingService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_embedding_text(perfume_data: dict) -> str:
    """
    Формирует текст для генерации embedding.

    Args:
        perfume_data: Словарь с данными аромата

    Returns:
        Текст для векторизации
    """
    top_notes = perfume_data.get('top_notes') or 'нет'
    middle_notes = perfume_data.get('middle_notes') or 'нет'
    base_notes = perfume_data.get('base_notes') or 'нет'

    tags = perfume_data.get('tags') or ''

    text = f"""Аромат: {perfume_data['name']}
Бренд: {perfume_data['brand']}
Пол: {perfume_data.get('gender') or 'неизвестен'}
Год: {perfume_data.get('year') or 'неизвестен'}
Семейство: {perfume_data.get('family') or 'неизвестно'}
Категория: {perfume_data.get('category') or 'неизвестна'}
Тип: {perfume_data.get('product_type') or 'неизвестен'}
Верхние ноты: {top_notes}
Средние ноты: {middle_notes}
Базовые ноты: {base_notes}
Характер: {tags or 'нет тегов'}
Описание: {perfume_data.get('description') or 'нет описания'}""".strip()

    return text


def get_perfumes_with_notes(session, force: bool = False):
    """
    Получить все ароматы с нотами из БД.

    Args:
        session: SQLAlchemy session
        force: Если True, получить все ароматы (включая с embeddings)

    Returns:
        List[dict]: Список ароматов с нотами
    """
    # ИСПРАВЛЕНО: pn.level вместо pn.note_type
    # ИСПРАВЛЕНО: 'Top', 'Middle', 'Base' вместо lowercase
    query = text("""
    SELECT
        p.id,
        p.name,
        p.brand,
        p.year,
        p.gender,
        p.family,
        p.description,
        p.category,
        p.product_type,
        string_agg(DISTINCT CASE WHEN pn.level = 'Top' THEN n.name END, ', ') AS top_notes,
        string_agg(DISTINCT CASE WHEN pn.level = 'Middle' THEN n.name END, ', ') AS middle_notes,
        string_agg(DISTINCT CASE WHEN pn.level = 'Base' THEN n.name END, ', ') AS base_notes,
        (SELECT string_agg(pt.tag, ', ' ORDER BY pt.confidence DESC)
         FROM perfume_tags pt WHERE pt.perfume_id = p.id) AS tags
    FROM perfumes p
    LEFT JOIN perfume_notes pn ON pn.perfume_id = p.id
    LEFT JOIN notes n ON n.id = pn.note_id
    """ + ("" if force else """
    WHERE NOT EXISTS (
        SELECT 1 FROM perfume_embeddings pe WHERE pe.perfume_id = p.id
    )
    """) + """
    GROUP BY p.id, p.name, p.brand, p.year, p.gender, p.family, p.description, p.category, p.product_type
    ORDER BY p.id
    """)

    result = session.execute(query)

    perfumes = []
    for row in result:
        perfumes.append({
            'id': row[0],
            'name': row[1],
            'brand': row[2],
            'year': row[3],
            'gender': row[4],
            'family': row[5],
            'description': row[6],
            'category': row[7],
            'product_type': row[8],
            'top_notes': row[9],
            'middle_notes': row[10],
            'base_notes': row[11],
            'tags': row[12],
        })

    return perfumes


def save_embedding(session, perfume_id: int, embedding: List[float]):
    """
    Сохранить embedding в БД.

    Args:
        session: SQLAlchemy session
        perfume_id: ID аромата
        embedding: Вектор embedding
    """
    # Формат для pgvector: '[0.1, 0.2, 0.3]'
    embedding_str = '[' + ','.join(map(str, embedding)) + ']'

    # Используем raw SQL с форматированием, т.к. pgvector требует cast
    query = text(f"""
    INSERT INTO perfume_embeddings (perfume_id, embedding)
    VALUES (:perfume_id, '{embedding_str}'::vector)
    ON CONFLICT (perfume_id)
    DO UPDATE SET embedding = EXCLUDED.embedding
    """)

    session.execute(query, {'perfume_id': perfume_id})


def ensure_embedding_table(session, dimension: int):
    """
    Проверить/создать таблицу для embeddings с нужной размерностью.

    Args:
        session: SQLAlchemy session
        dimension: Размерность вектора (312 для rubert-tiny2)
    """
    # Проверяем существование таблицы
    check_query = text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'perfume_embeddings'
        )
    """)
    exists = session.execute(check_query).scalar()

    if not exists:
        logger.info(f"Создание таблицы perfume_embeddings с размерностью {dimension}...")
        create_query = text(f"""
            CREATE TABLE perfume_embeddings (
                id SERIAL PRIMARY KEY,
                perfume_id INTEGER UNIQUE NOT NULL REFERENCES perfumes(id) ON DELETE CASCADE,
                embedding VECTOR({dimension}) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        session.execute(create_query)

        # Создаем HNSW индекс для быстрого поиска
        index_query = text("""
            CREATE INDEX IF NOT EXISTS perfume_embeddings_hnsw_idx
            ON perfume_embeddings
            USING hnsw (embedding vector_cosine_ops)
        """)
        session.execute(index_query)
        session.commit()
        logger.info("Таблица и индекс созданы")
    else:
        # Проверяем размерность существующей таблицы
        dim_query = text("""
            SELECT atttypmod
            FROM pg_attribute
            WHERE attrelid = 'perfume_embeddings'::regclass
            AND attname = 'embedding'
        """)
        current_dim = session.execute(dim_query).scalar()

        if current_dim and current_dim != dimension:
            logger.warning(f"Текущая размерность {current_dim} отличается от {dimension}")
            logger.info("Изменение размерности колонки...")

            # Очищаем таблицу и меняем тип
            session.execute(text("DELETE FROM perfume_embeddings"))
            session.execute(text(f"""
                ALTER TABLE perfume_embeddings
                ALTER COLUMN embedding TYPE VECTOR({dimension})
            """))
            session.commit()
            logger.info(f"Размерность изменена на {dimension}")


def main():
    parser = argparse.ArgumentParser(
        description="Генерация embeddings для ароматов"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Размер батча для обработки (default: 50)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="cointegrated/rubert-tiny2",
        help="Модель sentence-transformers (default: rubert-tiny2)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Перегенерировать существующие embeddings"
    )

    args = parser.parse_args()

    # Загрузить .env
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL")

    if not DATABASE_URL:
        logger.error("DATABASE_URL не найден в .env")
        sys.exit(1)

    # Подключение к БД
    engine = create_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. Инициализация сервиса
        logger.info("=" * 60)
        logger.info("ГЕНЕРАЦИЯ EMBEDDINGS")
        logger.info("=" * 60)

        embedding_service = SentenceTransformerEmbeddingService(args.model)
        dimension = embedding_service.dimension

        # 2. Проверить/создать таблицу
        ensure_embedding_table(session, dimension)

        # 3. Получить ароматы
        logger.info("Загрузка ароматов из БД...")
        perfumes = get_perfumes_with_notes(session, force=args.force)
        logger.info(f"Найдено ароматов для обработки: {len(perfumes)}")

        if not perfumes:
            logger.info("Нет ароматов для обработки!")
            return

        # 4. Генерация embeddings
        logger.info(f"Размерность embeddings: {dimension}")
        logger.info(f"Размер батча: {args.batch_size}")
        logger.info("")

        success_count = 0
        error_count = 0

        # Обработка батчами
        for i in range(0, len(perfumes), args.batch_size):
            batch = perfumes[i:i + args.batch_size]
            batch_num = i // args.batch_size + 1
            total_batches = (len(perfumes) + args.batch_size - 1) // args.batch_size

            try:
                # Формирование текстов
                texts = [create_embedding_text(p) for p in batch]

                # Генерация embeddings (батч)
                logger.info(f"Батч {batch_num}/{total_batches}: генерация embeddings...")
                embeddings = embedding_service.generate_embeddings_batch(texts)

                # Сохранение в БД
                for perfume, embedding in zip(batch, embeddings):
                    try:
                        save_embedding(session, perfume['id'], embedding)
                        success_count += 1
                        logger.info(f"  [{success_count}/{len(perfumes)}] {perfume['brand']} - {perfume['name']}")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"  {perfume['name']}: {e}")

                session.commit()

            except Exception as e:
                session.rollback()
                error_count += len(batch)
                logger.error(f"Ошибка обработки батча: {e}")

        logger.info("")
        logger.info("=" * 60)
        logger.info("ИТОГИ")
        logger.info("=" * 60)
        logger.info(f"Успешно: {success_count}")
        logger.info(f"Ошибки: {error_count}")

        # Статистика по БД
        count = session.execute(text("SELECT COUNT(*) FROM perfume_embeddings")).scalar()
        logger.info(f"Всего embeddings в БД: {count}")

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()
