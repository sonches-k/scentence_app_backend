"""
Подготовка тестовых пользователей для нагрузочного тестирования.

Скрипт подключается напрямую к БД, создаёт N тестовых пользователей
(email вида loadtest_NNN@loadtest.scentence), вставляет для каждого
известный код верификации, получает JWT-токены через API и сохраняет
их вместе с выборкой perfume_id в scripts/load_test_tokens.json.

Предварительно: запустить backend (docker-compose up -d).

Запуск:
    python scripts/create_load_test_users.py
    python scripts/create_load_test_users.py --count 20 --url http://localhost:8000
    python scripts/create_load_test_users.py --cleanup   # только удалить старых тестовых пользователей
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5433/perfume_db",
)
DEFAULT_API_URL = "http://localhost:8000"
TEST_EMAIL_DOMAIN = "loadtest.scentence"
VERIFICATION_CODE = "777777"
DEFAULT_COUNT = 10
DEFAULT_PERFUME_SAMPLE = 50
OUTPUT_PATH = Path(__file__).parent / "load_test_tokens.json"


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Создать тестовых пользователей и сохранить JWT-токены для locust"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Число тестовых пользователей (по умолчанию {DEFAULT_COUNT})",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_API_URL,
        help=f"Базовый URL запущенного API (по умолчанию {DEFAULT_API_URL})",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_PATH),
        help=f"Путь к выходному JSON-файлу (по умолчанию {OUTPUT_PATH})",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Только удалить тестовых пользователей из БД и выйти",
    )
    return parser.parse_args()


# ── DB helpers ───────────────────────────────────────────────────────────────

def make_session(db_url: str) -> Session:
    engine = create_engine(db_url, pool_pre_ping=True)
    return sessionmaker(bind=engine)()


def cleanup_test_users(session: Session) -> int:
    """Удалить всех пользователей с email в домене TEST_EMAIL_DOMAIN."""
    result = session.execute(
        text("DELETE FROM users WHERE email LIKE :pattern"),
        {"pattern": f"%@{TEST_EMAIL_DOMAIN}"},
    )
    session.execute(
        text("DELETE FROM verification_codes WHERE email LIKE :pattern"),
        {"pattern": f"%@{TEST_EMAIL_DOMAIN}"},
    )
    session.commit()
    return result.rowcount


def upsert_verification_code(session: Session, email: str) -> None:
    """Вставить (или заменить) код верификации с известным значением."""
    session.execute(
        text("DELETE FROM verification_codes WHERE email = :email"),
        {"email": email},
    )
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    session.execute(
        text(
            "INSERT INTO verification_codes (email, code, expires_at, attempts) "
            "VALUES (:email, :code, :expires_at, 0)"
        ),
        {"email": email, "code": VERIFICATION_CODE, "expires_at": expires_at},
    )
    session.commit()


def fetch_perfume_ids(session: Session, count: int) -> list[int]:
    """Случайная выборка perfume_id из БД для тестов просмотра."""
    rows = session.execute(
        text("SELECT id FROM perfumes ORDER BY RANDOM() LIMIT :n"),
        {"n": count},
    ).fetchall()
    return [row[0] for row in rows]


# ── API helpers ───────────────────────────────────────────────────────────────

def check_health(base_url: str) -> bool:
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


def verify_and_get_tokens(base_url: str, email: str) -> dict | None:
    """Вызвать /auth/verify и вернуть {access_token, refresh_token} или None."""
    try:
        r = requests.post(
            f"{base_url}/api/v1/auth/verify",
            json={"email": email, "code": VERIFICATION_CODE},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
        print(f"  [!] {email}: /verify вернул {r.status_code} — {r.text[:120]}")
        return None
    except requests.exceptions.RequestException as exc:
        print(f"  [!] {email}: ошибка запроса — {exc}")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()
    session = make_session(DATABASE_URL)

    if args.cleanup:
        removed = cleanup_test_users(session)
        print(f"[+] Удалено тестовых пользователей: {removed}")
        return 0

    print(f"[~] Подключение к БД: {DATABASE_URL[:DATABASE_URL.rfind('@') + 1]}***")
    print(f"[~] API: {args.url}")
    print(f"[~] Создаём {args.count} тестовых пользователей...")

    if not check_health(args.url):
        print(
            f"[X] Backend недоступен ({args.url}/health). "
            "Убедитесь, что сервер запущен.",
            file=sys.stderr,
        )
        return 2

    # Удалить устаревших тестовых пользователей
    removed = cleanup_test_users(session)
    if removed:
        print(f"[~] Удалено старых тестовых пользователей: {removed}")

    tokens: list[dict] = []
    for i in range(1, args.count + 1):
        email = f"loadtest_{i:03d}@{TEST_EMAIL_DOMAIN}"
        upsert_verification_code(session, email)
        result = verify_and_get_tokens(args.url, email)
        if result:
            tokens.append({
                "email": email,
                "access_token": result["access_token"],
                "refresh_token": result["refresh_token"],
            })
            print(f"  [{i:2d}/{args.count}] {email} — OK")
        else:
            print(f"  [{i:2d}/{args.count}] {email} — FAIL (пропускаем)")

    perfume_ids = fetch_perfume_ids(session, DEFAULT_PERFUME_SAMPLE)
    session.close()

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_url": args.url,
        "tokens": tokens,
        "perfume_ids": perfume_ids,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[+] Токены сохранены: {out_path}")
    print(f"[+] Пользователей с токенами: {len(tokens)}/{args.count}")
    print(f"[+] Perfume ID для браузинга: {len(perfume_ids)}")
    if len(tokens) == 0:
        print("[X] Нет ни одного валидного токена — нагрузочный тест авторизованных сценариев невозможен.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
