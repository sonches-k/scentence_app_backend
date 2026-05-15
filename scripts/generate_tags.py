"""
Генерация эмоциональных тегов и суммаризации для ароматов через DeepSeek.

Для каждого аромата:
  1. Собирает текст (название, бренд, ноты, описание)
  2. Отправляет в DeepSeek API
  3. Сохраняет теги в perfume_tags (source='deepseek')
  4. Сохраняет суммаризацию в perfumes.review_summary

Использование:
    python scripts/generate_tags.py --dry-run         # без запросов к API
    python scripts/generate_tags.py --limit 5         # только 5 ароматов
    python scripts/generate_tags.py --limit 5 --dry-run
    python scripts/generate_tags.py                   # все ароматы
    python scripts/generate_tags.py --force           # перезаписать существующие теги
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 20
BATCH_DELAY = 0.5   # секунд между батчами (rate limit DeepSeek)
MAX_RETRIES = 3
RETRY_DELAY = 2.0   # секунд между повторами


# ---------------------------------------------------------------------------
# БД: подготовка
# ---------------------------------------------------------------------------

def ensure_summary_column(session) -> None:
    """Добавить колонку review_summary в perfumes если её нет."""
    try:
        session.execute(text("""
            ALTER TABLE perfumes
            ADD COLUMN IF NOT EXISTS review_summary TEXT
        """))
        session.commit()
        logger.info("Колонка review_summary проверена/добавлена")
    except Exception as e:
        session.rollback()
        logger.warning(f"Не удалось добавить колонку review_summary: {e}")


def get_perfumes(
    session,
    force: bool = False,
    limit: int = None,
    offset: int = 0,
    only_truncated: bool = False,
    fix_style: bool = False,
    missing_summary: bool = False,
) -> list[dict]:
    """
    Загрузить ароматы из БД вместе с нотами.

    Если force=False — пропускает ароматы, у которых уже есть теги source='deepseek'.
    only_truncated=True — только ароматы с review_summary длиной >= 295 символов (обрезанные).
    fix_style=True — только ароматы с summary в разговорном стиле (начинаются с «Представь»/«Слушай»).
    offset позволяет запускать несколько процессов параллельно на разных диапазонах.
    """
    if fix_style:
        already_tagged_filter = (
            "WHERE p.review_summary ILIKE 'слушай%' OR p.review_summary ILIKE 'представь%'"
        )
    elif only_truncated:
        already_tagged_filter = "WHERE LENGTH(p.review_summary) >= 295"
    elif missing_summary:
        already_tagged_filter = "WHERE p.review_summary IS NULL"
    elif force:
        already_tagged_filter = ""
    else:
        already_tagged_filter = """
    WHERE NOT EXISTS (
        SELECT 1 FROM perfume_tags pt
        WHERE pt.perfume_id = p.id AND pt.source = 'deepseek'
    )
    """
    limit_clause = f"LIMIT {limit}" if limit else ""
    offset_clause = f"OFFSET {offset}" if offset else ""

    query = text(f"""
        SELECT
            p.id,
            p.name,
            p.brand,
            p.family,
            p.description,
            string_agg(CASE WHEN pn.level = 'Top'    THEN n.name END, ', ') AS top_notes,
            string_agg(CASE WHEN pn.level = 'Middle'  THEN n.name END, ', ') AS middle_notes,
            string_agg(CASE WHEN pn.level = 'Base'    THEN n.name END, ', ') AS base_notes
        FROM perfumes p
        LEFT JOIN perfume_notes pn ON pn.perfume_id = p.id
        LEFT JOIN notes n ON n.id = pn.note_id
        {already_tagged_filter}
        GROUP BY p.id, p.name, p.brand, p.family, p.description
        ORDER BY p.id
        {limit_clause}
        {offset_clause}
    """)

    rows = session.execute(query).fetchall()
    return [
        {
            "id":           row[0],
            "name":         row[1],
            "brand":        row[2],
            "family":       row[3] or "неизвестно",
            "description":  row[4] or "",
            "top_notes":    row[5] or "нет",
            "middle_notes": row[6] or "нет",
            "base_notes":   row[7] or "нет",
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# DeepSeek: промт и вызов
# ---------------------------------------------------------------------------

def build_prompt(perfume: dict, summary_only: bool = False) -> str:
    description = perfume["description"][:500] if perfume["description"] else "нет описания"
    base = (
        f"Аромат: {perfume['name']} от {perfume['brand']}\n"
        f"Семейство: {perfume['family']}\n"
        f"Ноты: верхние — {perfume['top_notes']}, "
        f"средние — {perfume['middle_notes']}, "
        f"базовые — {perfume['base_notes']}\n"
        f"Описание: {description}\n\n"
    )
    if summary_only:
        return (
            "Ты — эксперт по парфюмерии. Напиши короткое описание впечатления от аромата: "
            "1-2 предложения, на русском, нейтральный тон, без обращений и восклицаний, "
            "без слов «Слушай», «Представь», «Это». Начни сразу с характера аромата.\n\n"
            + base
            + 'Ответь ТОЛЬКО JSON: {"summary": "текст"}'
        )
    return (
        "Ты — эксперт по парфюмерии. На основе описания аромата определи:\n"
        "1. До 10 эмоциональных тегов/ассоциаций — короткие слова или фразы "
        "(примеры: уютный, романтичный, офисный, загадочный, вечерний, свежий, "
        "дерзкий, элегантный, для свидания, на каждый день)\n"
        "2. Короткое описание впечатления: 1-2 предложения, нейтральный тон, "
        "без обращений и восклицаний, без слов «Слушай», «Представь», «Это». "
        "Начни сразу с характера аромата.\n\n"
        + base
        + 'Ответь ТОЛЬКО JSON: {"tags": ["тег1", "..."], "summary": "текст"}'
    )


_SUMMARY_LIMIT = 800

def _truncate_summary(text: str) -> str:
    if len(text) <= _SUMMARY_LIMIT:
        return text
    truncated = text[:_SUMMARY_LIMIT]
    last = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
    return truncated[: last + 1] if last != -1 else truncated


def _extract_json(content: str) -> str:
    """Извлечь JSON из ответа (убрать markdown-обёртку если есть)."""
    if "```" in content:
        for part in content.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                return part
    return content


def call_deepseek(client, model: str, prompt: str, summary_only: bool = False) -> dict | None:
    """
    Вызвать DeepSeek API. Retry до MAX_RETRIES раз.
    Возвращает {"tags": [...], "summary": "..."} или None при неудаче.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200 if summary_only else 700,
                temperature=0.6,
            )
            content = response.choices[0].message.content.strip()
            content = _extract_json(content)
            data = json.loads(content)

            summary = _truncate_summary(str(data.get("summary", "")).strip())

            if summary_only:
                return {"tags": [], "summary": summary}

            tags = data.get("tags", [])
            if not isinstance(tags, list):
                raise ValueError("поле 'tags' должно быть списком")
            tags = [str(t).strip() for t in tags if str(t).strip()][:10]

            return {"tags": tags, "summary": summary}

        except json.JSONDecodeError as e:
            logger.warning(f"    Попытка {attempt}/{MAX_RETRIES}: невалидный JSON — {e}")
        except Exception as e:
            logger.warning(f"    Попытка {attempt}/{MAX_RETRIES}: ошибка API — {e}")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * attempt)

    return None


# ---------------------------------------------------------------------------
# БД: сохранение
# ---------------------------------------------------------------------------

def save_tags(session, perfume_id: int, tags: list[str], force: bool) -> None:
    """Сохранить теги в perfume_tags с source='deepseek'."""
    if force:
        session.execute(text("""
            DELETE FROM perfume_tags
            WHERE perfume_id = :pid AND source = 'deepseek'
        """), {"pid": perfume_id})

    for tag in tags:
        session.execute(text("""
            INSERT INTO perfume_tags (perfume_id, tag, source)
            VALUES (:pid, :tag, 'deepseek')
            ON CONFLICT ON CONSTRAINT _perfume_tag_uc DO NOTHING
        """), {"pid": perfume_id, "tag": tag})


def save_summary(session, perfume_id: int, summary: str) -> None:
    """Сохранить суммаризацию в perfumes.review_summary."""
    session.execute(text("""
        UPDATE perfumes
        SET review_summary = :summary
        WHERE id = :pid
    """), {"summary": summary, "pid": perfume_id})


# ---------------------------------------------------------------------------
# Обработка батча
# ---------------------------------------------------------------------------

def process_perfume(
    session,
    client,
    model: str,
    perfume: dict,
    dry_run: bool,
    force: bool,
    idx: int,
    total: int,
    summary_only: bool = False,
) -> bool:
    """Обработать один аромат. Возвращает True при успехе."""
    label = f"[{idx}/{total}] {perfume['brand']} — {perfume['name']}"
    prompt = build_prompt(perfume, summary_only=summary_only)

    if dry_run:
        logger.info(f"  [DRY-RUN] {label}")
        logger.info(f"            промт ({len(prompt)} симв.): {prompt[:150].replace(chr(10), ' ')}…")
        return True

    result = call_deepseek(client, model, prompt, summary_only=summary_only)
    if result is None:
        logger.error(f"  ОШИБКА: {label} — нет ответа после {MAX_RETRIES} попыток")
        return False

    try:
        if not summary_only:
            save_tags(session, perfume["id"], result["tags"], force)
        save_summary(session, perfume["id"], result["summary"])
        session.commit()

        tags_str = ", ".join(result["tags"]) or "—"
        logger.info(f"  OK  {label}")
        logger.info(f"      теги: {tags_str}")
        logger.info(f"      summary: {result['summary'][:90]}…")
        return True

    except Exception as e:
        session.rollback()
        logger.error(f"  ОШИБКА БД: {label} — {e}")
        return False


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Генерация эмоциональных тегов и суммаризации через DeepSeek"
    )
    parser.add_argument(
        "--limit", "-n",
        type=int,
        default=None,
        metavar="N",
        help="Обработать только N ароматов",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Показать что будет отправлено — без реальных запросов к API",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Перезаписать существующие теги DeepSeek",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Размер батча (default: {BATCH_SIZE})",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        metavar="N",
        help="Пропустить первые N ароматов (для параллельного запуска)",
    )
    parser.add_argument(
        "--only-truncated",
        action="store_true",
        help="Обработать только ароматы с обрезанным summary (>= 295 символов)",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Генерировать только summary, теги не трогать",
    )
    parser.add_argument(
        "--fix-style",
        action="store_true",
        help="Перегенерировать summary начинающиеся с «Слушай» или «Представь»",
    )
    parser.add_argument(
        "--missing-summary",
        action="store_true",
        help="Генерировать summary только для ароматов где оно NULL",
    )
    args = parser.parse_args()

    # Загружаем .env из корня проекта (override=True чтобы .env имел приоритет над env в терминале)
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)

    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        logger.error("DATABASE_URL не найден в .env")
        sys.exit(1)
    # При запуске на хосте подключаемся к Docker Postgres на порту 5433 (в docker-compose: 5433:5432)
    if "@postgres:" in DATABASE_URL or "@postgres/" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("@postgres:5432", "@127.0.0.1:5433").replace("@postgres/", "@127.0.0.1:5433/")
        logger.info("DATABASE_URL: подключение к Docker Postgres на 127.0.0.1:5433")
    elif "localhost:5432" in DATABASE_URL or "127.0.0.1:5432" in DATABASE_URL:
        # В .env указан localhost:5432 — на Mac там часто локальный PG без роли postgres; используем порт Docker
        DATABASE_URL = DATABASE_URL.replace("localhost:5432", "127.0.0.1:5433").replace("127.0.0.1:5432", "127.0.0.1:5433")
        logger.info("DATABASE_URL: порт 5432 заменён на 5433 (Docker Postgres)")

    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    if not DEEPSEEK_API_KEY and not args.dry_run:
        logger.error("DEEPSEEK_API_KEY не найден в .env (или используй --dry-run)")
        sys.exit(1)

    # Клиент DeepSeek (OpenAI-совместимый)
    client = None
    if not args.dry_run:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

    engine = create_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        logger.info("=" * 60)
        logger.info("ГЕНЕРАЦИЯ ТЕГОВ И СУММАРИЗАЦИИ (DeepSeek)")
        if args.dry_run:
            logger.info("РЕЖИМ: DRY-RUN — запросы к API не отправляются")
        if args.force:
            logger.info("РЕЖИМ: FORCE — существующие теги будут перезаписаны")
        if args.only_truncated:
            logger.info("РЕЖИМ: ONLY-TRUNCATED — только ароматы с обрезанным summary")
        if args.summary_only:
            logger.info("РЕЖИМ: SUMMARY-ONLY — теги не затрагиваются")
        if args.fix_style:
            logger.info("РЕЖИМ: FIX-STYLE — перегенерация summary в разговорном стиле")
        if args.missing_summary:
            logger.info("РЕЖИМ: MISSING-SUMMARY — только ароматы без summary")
        logger.info(f"Модель: {DEEPSEEK_MODEL}")
        logger.info("=" * 60)

        if not args.dry_run:
            ensure_summary_column(session)

        logger.info("Загрузка ароматов из БД...")
        perfumes = get_perfumes(
            session,
            force=args.force,
            limit=args.limit,
            offset=args.offset,
            only_truncated=args.only_truncated,
            fix_style=args.fix_style,
            missing_summary=args.missing_summary,
        )

        if not perfumes:
            logger.info(
                "Нет ароматов для обработки. "
                "Все уже обработаны? Используй --force для перезаписи."
            )
            return

        total = len(perfumes)
        logger.info(f"Ароматов к обработке: {total}")
        logger.info(f"Батч: {args.batch_size}, задержка: {BATCH_DELAY}с")
        logger.info("")

        success_count = 0
        error_count = 0
        total_batches = (total + args.batch_size - 1) // args.batch_size

        for batch_idx in range(0, total, args.batch_size):
            batch = perfumes[batch_idx : batch_idx + args.batch_size]
            batch_num = batch_idx // args.batch_size + 1

            logger.info(f"--- Батч {batch_num}/{total_batches} ({len(batch)} ароматов) ---")

            for i, perfume in enumerate(batch):
                global_idx = batch_idx + i + 1
                ok = process_perfume(
                    session, client, DEEPSEEK_MODEL,
                    perfume, args.dry_run, args.force,
                    global_idx, total,
                    summary_only=args.summary_only,
                )
                if ok:
                    success_count += 1
                else:
                    error_count += 1

            # Пауза между батчами (кроме последнего)
            if batch_num < total_batches and not args.dry_run:
                logger.info(f"Пауза {BATCH_DELAY}с (rate limit)…")
                time.sleep(BATCH_DELAY)

            logger.info("")

        logger.info("=" * 60)
        logger.info("ИТОГИ")
        logger.info("=" * 60)
        logger.info(f"Успешно:  {success_count}")
        logger.info(f"Ошибок:   {error_count}")
        logger.info(f"Всего:    {total}")

        if not args.dry_run:
            tag_count = session.execute(
                text("SELECT COUNT(*) FROM perfume_tags WHERE source = 'deepseek'")
            ).scalar()
            summary_count = session.execute(
                text("SELECT COUNT(*) FROM perfumes WHERE review_summary IS NOT NULL")
            ).scalar()
            logger.info(f"Тегов DeepSeek в БД: {tag_count}")
            logger.info(f"Ароматов с суммаризацией: {summary_count}")

    except KeyboardInterrupt:
        logger.info("\nПрерывание пользователем (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
