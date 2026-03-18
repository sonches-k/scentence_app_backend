"""
Загрузка данных из JSON в PostgreSQL.

Использование:
    python scripts/load_to_db.py                                     # Загрузить данные (perfumes.json)
    python scripts/load_to_db.py --input perfumes.json               # Явно указать файл
    python scripts/load_to_db.py --clear                             # Очистить БД перед загрузкой
    python scripts/load_to_db.py --skip-embeddings                   # Без генерации эмбеддингов
    python scripts/load_to_db.py --input perfumes.json --clear --skip-embeddings
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.infrastructure.database.connection import engine, SessionLocal
from parsers.filters import is_sample_pack_or_set
from parsers.normalize import normalize_perfume_name, clean_perfume_notes, normalize_family

_CYRILLIC_DOMAINS = {
    "духи.рф": "xn--d1ai6ai.xn--p1ai",
}


def _punycode_url(url: str | None) -> str | None:
    """Заменить кириллические домены на punycode для совместимости с браузерами."""
    if not url:
        return url
    for cyrillic, puny in _CYRILLIC_DOMAINS.items():
        if cyrillic in url:
            url = url.replace(cyrillic, puny)
    return url

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def ensure_columns(session):
    """Добавить колонки price, category, source_url если их нет."""
    try:
        session.execute(text("ALTER TABLE perfumes ADD COLUMN IF NOT EXISTS price FLOAT"))
        session.execute(text("ALTER TABLE perfumes ADD COLUMN IF NOT EXISTS category VARCHAR(100)"))
        session.execute(text("ALTER TABLE perfumes ADD COLUMN IF NOT EXISTS source_url VARCHAR(512)"))
        session.commit()
        logger.info("Колонки price, category, source_url проверены/добавлены")
    except SQLAlchemyError as e:
        session.rollback()
        logger.warning(f"Не удалось добавить колонки: {e}")


def clean_database(session):
    """Очистить таблицы перед загрузкой."""
    logger.info("Очистка базы данных...")
    try:
        # Удаляем в правильном порядке (сначала зависимые)
        session.execute(text("DELETE FROM perfume_notes"))
        session.execute(text("DELETE FROM perfume_embeddings"))
        session.execute(text("DELETE FROM perfume_tags"))
        session.execute(text("DELETE FROM user_favorites"))
        session.execute(text("DELETE FROM perfumes"))
        session.execute(text("DELETE FROM notes"))
        session.commit()
        logger.info("✓ База данных очищена")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Ошибка при очистке БД: {e}")
        raise


def get_or_create_note(session, note_name: str) -> int:
    """
    Получить ID ноты или создать новую.
    Использует INSERT ... ON CONFLICT для дедупликации.
    """
    note_name = note_name.strip().lower()
    if not note_name:
        return None

    try:
        # Пробуем вставить, при конфликте возвращаем существующий ID
        result = session.execute(text("""
            INSERT INTO notes (name)
            VALUES (:name)
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """), {"name": note_name})

        note_id = result.scalar()
        return note_id
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при создании ноты '{note_name}': {e}")
        return None


def insert_perfume(session, perfume_data: dict) -> int:
    """
    Вставить аромат в БД.
    Возвращает ID созданного аромата.
    """
    try:
        source_url = perfume_data.get("source_url")
        if isinstance(source_url, list):
            source_url = source_url[0] if source_url else None

        result = session.execute(text("""
            INSERT INTO perfumes (name, brand, year, gender, family, description, image_url, source_url, price, product_type, category)
            VALUES (:name, :brand, :year, :gender, :family, :description, :image_url, :source_url, :price, :product_type, :category)
            RETURNING id
        """), {
            "name": perfume_data.get("name"),
            "brand": perfume_data.get("brand"),
            "year": perfume_data.get("year"),
            "gender": perfume_data.get("gender"),
            "family": perfume_data.get("family"),
            "description": perfume_data.get("description"),
            "image_url": _punycode_url(perfume_data.get("image_url")),
            "source_url": _punycode_url(source_url),
            "price": perfume_data.get("price"),
            "product_type": perfume_data.get("product_type"),
            "category": perfume_data.get("category"),
        })

        perfume_id = result.scalar()
        return perfume_id
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при вставке аромата '{perfume_data.get('name')}': {e}")
        raise


def insert_perfume_note(session, perfume_id: int, note_id: int, level: str):
    """Связать аромат с нотой."""
    try:
        session.execute(text("""
            INSERT INTO perfume_notes (perfume_id, note_id, level)
            VALUES (:perfume_id, :note_id, :level)
            ON CONFLICT DO NOTHING
        """), {
            "perfume_id": perfume_id,
            "note_id": note_id,
            "level": level,
        })
    except SQLAlchemyError as e:
        logger.warning(f"Ошибка при связывании ноты: {e}")


def load_perfume(session, perfume_data: dict) -> bool:
    """
    Загрузить один аромат со всеми нотами.
    Возвращает True при успехе.
    """
    try:
        # 1. Вставляем аромат
        perfume_id = insert_perfume(session, perfume_data)

        if not perfume_id:
            return False

        # 2. Обрабатываем ноты
        notes = perfume_data.get("notes", {})

        # Верхние ноты
        for note_name in notes.get("top", []):
            note_id = get_or_create_note(session, note_name)
            if note_id:
                insert_perfume_note(session, perfume_id, note_id, "Top")

        # Средние ноты
        for note_name in notes.get("middle", []):
            note_id = get_or_create_note(session, note_name)
            if note_id:
                insert_perfume_note(session, perfume_id, note_id, "Middle")

        # Базовые ноты
        for note_name in notes.get("base", []):
            note_id = get_or_create_note(session, note_name)
            if note_id:
                insert_perfume_note(session, perfume_id, note_id, "Base")

        # 3. Коммитим транзакцию
        session.commit()
        return True

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Ошибка при загрузке аромата: {e}")
        return False


def load_from_json(filepath: str, clean: bool = False, skip_embeddings: bool = False):
    """
    Основная функция загрузки данных из JSON.
    skip_embeddings=True — пропустить генерацию эмбеддингов (быстрая загрузка).
    """
    if skip_embeddings:
        logger.info("Режим --skip-embeddings: эмбеддинги не будут сгенерированы")

    # Проверяем файл
    path = Path(filepath)
    if not path.exists():
        logger.error(f"Файл не найден: {filepath}")
        return False

    # Читаем JSON
    logger.info(f"Загрузка данных из {filepath}...")
    with open(path, 'r', encoding='utf-8') as f:
        perfumes = json.load(f)

    logger.info(f"Найдено {len(perfumes)} ароматов в файле")

    # Создаём сессию
    session = SessionLocal()

    try:
        # Добавляем новые колонки если нужно
        ensure_columns(session)

        # Очищаем БД если нужно
        if clean:
            clean_database(session)

        # Загружаем ароматы
        success_count = 0
        error_count = 0

        for i, perfume in enumerate(perfumes, 1):
            name = perfume.get('name', 'Unknown')
            brand = perfume.get('brand', 'Unknown')

            if is_sample_pack_or_set(perfume):
                logger.debug(f"Пропуск набора/сэмпла: {brand} - {name}")
                continue

            if perfume.get("name") and perfume.get("brand"):
                perfume["name"] = normalize_perfume_name(perfume["name"], perfume["brand"])
            perfume["notes"] = clean_perfume_notes(perfume.get("notes"))
            perfume["family"] = normalize_family(perfume.get("family"))

            if load_perfume(session, perfume):
                success_count += 1
                logger.info(f"[{i}/{len(perfumes)}] ✓ {brand} - {name}")
            else:
                error_count += 1
                logger.error(f"[{i}/{len(perfumes)}] ✗ {brand} - {name}")

        # Итоги
        logger.info("=" * 50)
        logger.info("ИТОГИ ЗАГРУЗКИ:")
        logger.info(f"  Успешно: {success_count}")
        logger.info(f"  Ошибки: {error_count}")
        logger.info(f"  Всего: {len(perfumes)}")
        logger.info("=" * 50)

        # Статистика по БД
        perfume_count = session.execute(text("SELECT COUNT(*) FROM perfumes")).scalar()
        note_count = session.execute(text("SELECT COUNT(*) FROM notes")).scalar()
        link_count = session.execute(text("SELECT COUNT(*) FROM perfume_notes")).scalar()

        logger.info("СТАТИСТИКА БД:")
        logger.info(f"  Ароматов: {perfume_count}")
        logger.info(f"  Уникальных нот: {note_count}")
        logger.info(f"  Связей аромат-нота: {link_count}")

        return error_count == 0

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        session.rollback()
        return False

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Загрузка ароматов из JSON в PostgreSQL"
    )
    parser.add_argument(
        "--input", "--file", "-i",
        type=str,
        default="perfumes.json",
        dest="input",
        help="Путь к JSON файлу (по умолчанию: perfumes.json)"
    )
    parser.add_argument(
        "--clear", "--clean", "-c",
        action="store_true",
        dest="clear",
        help="Очистить таблицы БД перед загрузкой"
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        dest="skip_embeddings",
        help="Загрузить данные без генерации эмбеддингов"
    )

    args = parser.parse_args()

    # Определяем путь к файлу
    filepath = args.input
    if not Path(filepath).is_absolute():
        filepath = Path(__file__).parent.parent / filepath

    success = load_from_json(str(filepath), clean=args.clear, skip_embeddings=args.skip_embeddings)

    if success:
        logger.info("✅ Загрузка завершена успешно!")
    else:
        logger.error("❌ Загрузка завершена с ошибками")
        sys.exit(1)


if __name__ == "__main__":
    main()
