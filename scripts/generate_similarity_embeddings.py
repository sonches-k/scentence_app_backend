"""
Генерация similarity embeddings по нотному профилю аромата.

Используется для поиска похожих ароматов (без влияния бренда и описания).
Результат сохраняется в таблицу perfume_similarity_embeddings.

Использование:
    python scripts/generate_similarity_embeddings.py
    python scripts/generate_similarity_embeddings.py --batch-size 10
    python scripts/generate_similarity_embeddings.py --force
"""

import sys
import os
import argparse
import logging
from typing import List

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.infrastructure.external.embedding_service import SentenceTransformerEmbeddingService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_similarity_text(perfume_data: dict) -> str:
    top_notes = perfume_data.get('top_notes') or ''
    middle_notes = perfume_data.get('middle_notes') or ''
    base_notes = perfume_data.get('base_notes') or ''
    tags = perfume_data.get('tags') or ''

    parts = [
        f"Пол: {perfume_data.get('gender') or 'неизвестен'}",
        f"Семейство: {perfume_data.get('family') or 'неизвестно'}",
        f"Категория: {perfume_data.get('category') or 'неизвестна'}",
        f"Тип: {perfume_data.get('product_type') or 'неизвестен'}",
    ]

    if top_notes:
        parts.append(f"Верхние ноты: {top_notes}")
    if middle_notes:
        parts.append(f"Средние ноты: {middle_notes}")
    if base_notes:
        parts.append(f"Базовые ноты: {base_notes}")
    if tags:
        parts.append(f"Характер: {tags}")

    return "\n".join(parts)


def get_perfumes(session, force: bool = False):
    where_clause = "" if force else """
    WHERE NOT EXISTS (
        SELECT 1 FROM perfume_similarity_embeddings pse WHERE pse.perfume_id = p.id
    )
    """

    query = text(f"""
    SELECT
        p.id,
        p.gender,
        p.family,
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
    {where_clause}
    GROUP BY p.id, p.gender, p.family, p.category, p.product_type
    ORDER BY p.id
    """)

    rows = session.execute(query).fetchall()
    return [
        {
            'id': r[0],
            'gender': r[1],
            'family': r[2],
            'category': r[3],
            'product_type': r[4],
            'top_notes': r[5],
            'middle_notes': r[6],
            'base_notes': r[7],
            'tags': r[8],
        }
        for r in rows
    ]


def save_embedding(session, perfume_id: int, embedding: List[float]):
    embedding_str = '[' + ','.join(map(str, embedding)) + ']'
    query = text(f"""
    INSERT INTO perfume_similarity_embeddings (perfume_id, embedding)
    VALUES (:perfume_id, '{embedding_str}'::vector)
    ON CONFLICT (perfume_id)
    DO UPDATE SET embedding = EXCLUDED.embedding
    """)
    session.execute(query, {'perfume_id': perfume_id})


def ensure_table(session, dimension: int):
    exists = session.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'perfume_similarity_embeddings'
        )
    """)).scalar()

    if not exists:
        logger.info("Создание таблицы perfume_similarity_embeddings...")
        session.execute(text(f"""
            CREATE TABLE perfume_similarity_embeddings (
                id SERIAL PRIMARY KEY,
                perfume_id INTEGER UNIQUE NOT NULL REFERENCES perfumes(id) ON DELETE CASCADE,
                embedding VECTOR({dimension}) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS perfume_similarity_embeddings_hnsw_idx
            ON perfume_similarity_embeddings
            USING hnsw (embedding vector_cosine_ops)
        """))
        session.commit()
        logger.info("Таблица и HNSW индекс созданы")


def main():
    parser = argparse.ArgumentParser(description="Генерация similarity embeddings")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--model", type=str, default="intfloat/multilingual-e5-large")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        logger.error("DATABASE_URL не найден в .env")
        sys.exit(1)

    engine = create_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        logger.info("=" * 60)
        logger.info("ГЕНЕРАЦИЯ SIMILARITY EMBEDDINGS")
        logger.info("=" * 60)

        embedding_service = SentenceTransformerEmbeddingService(args.model)
        ensure_table(session, embedding_service.dimension)

        perfumes = get_perfumes(session, force=args.force)
        logger.info(f"Ароматов для обработки: {len(perfumes)}")

        if not perfumes:
            logger.info("Нет ароматов для обработки")
            return

        success_count = 0
        error_count = 0

        for i in range(0, len(perfumes), args.batch_size):
            batch = perfumes[i:i + args.batch_size]
            batch_num = i // args.batch_size + 1
            total_batches = (len(perfumes) + args.batch_size - 1) // args.batch_size

            try:
                texts = [create_similarity_text(p) for p in batch]
                logger.info(f"Батч {batch_num}/{total_batches}...")
                embeddings = embedding_service.generate_embeddings_batch(texts)

                for perfume, embedding in zip(batch, embeddings):
                    try:
                        save_embedding(session, perfume['id'], embedding)
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        logger.error(f"  id={perfume['id']}: {e}")

                session.commit()

            except Exception as e:
                session.rollback()
                error_count += len(batch)
                logger.error(f"Ошибка батча {batch_num}: {e}")

        logger.info("=" * 60)
        logger.info(f"Успешно: {success_count}, Ошибки: {error_count}")
        count = session.execute(text("SELECT COUNT(*) FROM perfume_similarity_embeddings")).scalar()
        logger.info(f"Всего в БД: {count}")

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
