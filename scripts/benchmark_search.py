"""
Нагрузочный замер времени отклика семантического поиска.

Назначение:
    Замер показателей производительности эндпоинта POST /api/v1/search/
    для подтверждения требования ТЗ п. 4.1.5.3 (p95 ≤ 10 секунд).

Методика:
    1. Прогрев (warmup) — N первых запросов исключаются из статистики, так как
       при первом обращении к моделям sentence-transformers и DeepSeek
       выполняется холодная инициализация (загрузка модели, открытие соединений).
    2. Основная серия — последовательная отправка уникальных запросов на русском
       языке без авторизации (без Bearer-токена), чтобы исключить влияние кэша
       Redis (кэш активен только для авторизованных пользователей).
    3. Для каждого запроса фиксируется wall-clock latency на стороне клиента
       через time.perf_counter().
    4. На основе собранных значений вычисляются перцентили p50, p90, p95, p99,
       среднее арифметическое, медиана, стандартное отклонение, min, max.
    5. Результаты выводятся в консоль и сохраняются в CSV-файл с временной меткой.

Запуск:
    python scripts/benchmark_search.py
    python scripts/benchmark_search.py --url http://localhost:8000 --warmup 3 --count 50
    python scripts/benchmark_search.py --output benchmark_results/run_2026_04_27.csv

Условия фиксируются в ПМИ: модель сервера, БД, объём данных, версия Python.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import requests


DEFAULT_URL = "http://localhost:8000"
SEARCH_PATH = "/api/v1/search/"
DEFAULT_LIMIT = 5
REQUEST_TIMEOUT = 90.0


QUERIES: list[str] = [
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
    "пачули и пачули старая школа классика",
    "морозный мятный ментоловый освежающий",
    "сандал и ваниль уютный домашний",
    "горький миндаль вишнёвый темный",
    "табачный кожаный мужской вечерний",
    "лаванда и розмарин фужерный классический",
    "белые цветы свадебный нежный",
    "грейпфрут и базилик утренний бодрящий",
    "пачули и амбра тёплый чувственный",
    "морской бриз и кокос отпускной",
    "пион и магнолия весенний свежий",
    "уд и шафран дорогой восточный",
    "имбирь и кардамон пряный согревающий",
    "берёзовый дёготь и можжевельник суровый северный",
    "крем-брюле и карамель сладкий десертный",
    "белый чай и бергамот лёгкий деловой",
    "малина и пион ягодный женский",
    "ветивер и бобы тонка тёмный загадочный",
    "огурец и арбуз летний свежий",
    "нероли и петитгрейн солнечный аромат",
    "табак и виски бар прокуренный",
    "ягоды можжевельника и сосна горный лес",
    "карамель и попкорн уютный детский",
    "мирра и ладан загадочный мистический",
    "шипровый аромат с дубовым мхом ретро",
    "молочный лактонный мягкий аромат",
    "перец и куркума пряный гастрономический",
    "сирень и ландыш весенний романтичный",
    "лавр и тимьян средиземноморский",
    "кокос и тиаре тропический пляжный",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Замер latency семантического поиска")
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Базовый URL backend (по умолчанию {DEFAULT_URL})",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=2,
        help="Число прогревочных запросов, исключаемых из статистики (по умолчанию 2)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Число замеряемых запросов (по умолчанию 50)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Параметр limit в каждом запросе (по умолчанию 5)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Путь к CSV-файлу для сохранения замеров (по умолчанию: benchmark_results/<timestamp>.csv)",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Не сохранять CSV-файл (только вывод в консоль)",
    )
    return parser.parse_args()


def percentile(sorted_values: list[float], p: float) -> float:
    """
    Вычислить перцентиль методом «ближайший индекс» (nearest-rank).

    Стандартный для нагрузочного тестирования метод: индекс = ceil(p/100 * N) - 1.
    Гарантирует, что результат — реальный замер из выборки (а не интерполяция).
    """
    if not sorted_values:
        raise ValueError("Пустая выборка")
    n = len(sorted_values)
    rank = max(1, min(n, int(-(-p / 100 * n // 1))))
    return sorted_values[rank - 1]


def check_health(base_url: str) -> bool:
    """Проверить, что backend доступен."""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def measure_one(
    base_url: str,
    query: str,
    limit: int,
) -> tuple[float, int, str | None]:
    """
    Выполнить один запрос и вернуть (latency_seconds, status_code, error_message).
    """
    url = f"{base_url}{SEARCH_PATH}"
    payload = {"query": query, "limit": limit}
    start = time.perf_counter()
    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        elapsed = time.perf_counter() - start
        if response.status_code != 200:
            return elapsed, response.status_code, response.text[:200]
        return elapsed, 200, None
    except requests.exceptions.Timeout:
        elapsed = time.perf_counter() - start
        return elapsed, 0, "client timeout"
    except requests.exceptions.RequestException as exc:
        elapsed = time.perf_counter() - start
        return elapsed, 0, f"{type(exc).__name__}: {exc}"


def run_benchmark(
    base_url: str,
    warmup: int,
    count: int,
    limit: int,
) -> list[dict]:
    """Выполнить серию замеров, вернуть список словарей с результатами."""
    queries = QUERIES.copy()
    if count + warmup > len(queries):
        print(
            f"[!] Запрошено {count + warmup} уникальных запросов, "
            f"но в наборе доступно только {len(queries)}. "
            f"Лишние запросы будут повторно использовать темы из набора.",
            file=sys.stderr,
        )
        repeats = (count + warmup) // len(queries) + 1
        queries = (queries * repeats)[: count + warmup]

    results: list[dict] = []

    if warmup > 0:
        print(f"[~] Прогрев: {warmup} запрос(ов), результаты не учитываются в статистике")
        for i in range(warmup):
            query = queries[i]
            latency, status, err = measure_one(base_url, query, limit)
            tag = f"WARMUP {i + 1}/{warmup}"
            if status == 200:
                print(f"  {tag}: {latency:6.2f} сек | OK   | {query[:60]}")
            else:
                print(f"  {tag}: {latency:6.2f} сек | FAIL ({status}) | {err}")

    print(f"\n[~] Замер: {count} запрос(ов)")
    for i in range(count):
        query = queries[warmup + i]
        latency, status, err = measure_one(base_url, query, limit)
        results.append(
            {
                "index": i + 1,
                "query": query,
                "latency_sec": round(latency, 4),
                "status": status,
                "error": err or "",
            }
        )
        marker = "OK  " if status == 200 else f"FAIL ({status})"
        print(f"  {i + 1:3d}/{count}: {latency:6.2f} сек | {marker} | {query[:60]}")

    return results


def print_statistics(results: list[dict]) -> dict[str, float]:
    """Распечатать статистику и вернуть её как словарь."""
    successful = [r["latency_sec"] for r in results if r["status"] == 200]
    failed = [r for r in results if r["status"] != 200]
    n_total = len(results)
    n_ok = len(successful)
    n_fail = len(failed)

    if not successful:
        print("\n[X] Нет успешных замеров — статистика не может быть вычислена.")
        return {}

    sorted_lat = sorted(successful)
    stats = {
        "total": n_total,
        "successful": n_ok,
        "failed": n_fail,
        "min": sorted_lat[0],
        "max": sorted_lat[-1],
        "mean": statistics.mean(sorted_lat),
        "median": statistics.median(sorted_lat),
        "stdev": statistics.stdev(sorted_lat) if n_ok > 1 else 0.0,
        "p50": percentile(sorted_lat, 50),
        "p90": percentile(sorted_lat, 90),
        "p95": percentile(sorted_lat, 95),
        "p99": percentile(sorted_lat, 99),
    }

    print("\n" + "=" * 64)
    print("РЕЗУЛЬТАТЫ ЗАМЕРА LATENCY ПОИСКА")
    print("=" * 64)
    print(f"  Всего запросов:           {n_total}")
    print(f"  Успешных:                 {n_ok}")
    print(f"  Неуспешных:               {n_fail}")
    print("-" * 64)
    print(f"  min                       {stats['min']:6.2f} сек")
    print(f"  median (p50)              {stats['p50']:6.2f} сек")
    print(f"  mean (среднее)            {stats['mean']:6.2f} сек")
    print(f"  p90                       {stats['p90']:6.2f} сек")
    print(f"  p95                       {stats['p95']:6.2f} сек  <- ключевая метрика ТЗ")
    print(f"  p99                       {stats['p99']:6.2f} сек")
    print(f"  max                       {stats['max']:6.2f} сек")
    print(f"  stdev                     {stats['stdev']:6.2f} сек")
    print("=" * 64)

    target = 10.0
    if stats["p95"] <= target:
        print(f"[OK]   p95 = {stats['p95']:.2f} сек <= {target:.0f} сек — требование 4.1.5.3 ВЫПОЛНЕНО")
    else:
        print(f"[FAIL] p95 = {stats['p95']:.2f} сек  > {target:.0f} сек — требование 4.1.5.3 НЕ ВЫПОЛНЕНО")
    print("=" * 64)

    return stats


def save_csv(
    results: list[dict],
    stats: dict[str, float],
    output_path: Path,
) -> None:
    """Сохранить детальные замеры и сводную статистику в CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["# Detailed measurements"])
        writer.writerow(["index", "query", "latency_sec", "status", "error"])
        for r in results:
            writer.writerow([r["index"], r["query"], r["latency_sec"], r["status"], r["error"]])
        writer.writerow([])
        writer.writerow(["# Summary"])
        writer.writerow(["metric", "value_sec"])
        for key in ("min", "p50", "mean", "p90", "p95", "p99", "max", "stdev"):
            if key in stats:
                writer.writerow([key, round(stats[key], 4)])
        writer.writerow(["total_requests", stats.get("total", 0)])
        writer.writerow(["successful", stats.get("successful", 0)])
        writer.writerow(["failed", stats.get("failed", 0)])

    print(f"\n[+] Замеры сохранены: {output_path}")


def main() -> int:
    args = parse_args()

    print(f"Замер производительности: {args.url}{SEARCH_PATH}")
    print(f"Параметры: warmup={args.warmup}, count={args.count}, limit={args.limit}\n")

    if not check_health(args.url):
        print(
            f"[X] Не удалось подключиться к {args.url}/health. "
            "Убедитесь, что backend запущен.",
            file=sys.stderr,
        )
        return 2

    results = run_benchmark(args.url, args.warmup, args.count, args.limit)
    stats = print_statistics(results)

    if not args.no_csv and stats:
        if args.output:
            output_path = Path(args.output)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path("benchmark_results") / f"search_{timestamp}.csv"
        save_csv(results, stats, output_path)

    return 0 if stats and stats.get("p95", float("inf")) <= 10.0 else 1


if __name__ == "__main__":
    sys.exit(main())
