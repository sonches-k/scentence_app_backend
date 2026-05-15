"""
Обрезает уже сохранённые summary до конца последнего предложения.
Не обращается к DeepSeek — только правит данные в БД.

Использование:
    python scripts/fix_truncated_summaries.py --dry-run   # показать без изменений
    python scripts/fix_truncated_summaries.py             # применить
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

_SENTENCE_ENDS = ".!?"


def trim_to_sentence(s: str) -> str:
    last = max(s.rfind(c) for c in _SENTENCE_ENDS)
    return s[: last + 1] if last != -1 else s


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Показать изменения без записи в БД")
    args = parser.parse_args()

    load_dotenv(Path(__file__).parent.parent / ".env", override=True)

    DATABASE_URL = os.getenv("DATABASE_URL", "")
    if "@postgres:" in DATABASE_URL or "@postgres/" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("@postgres:5432", "@127.0.0.1:5433").replace("@postgres/", "@127.0.0.1:5433/")
    elif "localhost:5432" in DATABASE_URL or "127.0.0.1:5432" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("localhost:5432", "127.0.0.1:5433").replace("127.0.0.1:5432", "127.0.0.1:5433")

    engine = create_engine(DATABASE_URL, echo=False)
    session = sessionmaker(bind=engine)()

    rows = session.execute(text(
        "SELECT id, review_summary FROM perfumes WHERE LENGTH(review_summary) >= 295"
    )).fetchall()

    logger.info(f"Найдено обрезанных summary: {len(rows)}")

    fixed = 0
    for perfume_id, summary in rows:
        trimmed = trim_to_sentence(summary)
        if trimmed == summary:
            continue
        logger.info(f"  id={perfume_id}: {len(summary)} → {len(trimmed)} символов")
        logger.info(f"    было:  …{summary[-60:]!r}")
        logger.info(f"    стало: …{trimmed[-60:]!r}")
        if not args.dry_run:
            session.execute(
                text("UPDATE perfumes SET review_summary = :s WHERE id = :id"),
                {"s": trimmed, "id": perfume_id},
            )
        fixed += 1

    if not args.dry_run:
        session.commit()
        logger.info(f"Готово. Исправлено: {fixed} из {len(rows)}")
    else:
        logger.info(f"[DRY-RUN] Будет исправлено: {fixed} из {len(rows)}")

    session.close()


if __name__ == "__main__":
    main()
