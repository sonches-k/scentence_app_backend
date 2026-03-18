FROM python:3.11-slim

# Системные зависимости для psycopg2, компиляции C-расширений
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Слой 1: тяжёлые ML-зависимости (torch + sentence-transformers)
# Выносим отдельно, чтобы не пересобирать при изменении остального кода.
# CPU-версия torch: ~700 MB вместо 2+ GB GPU-версии.
RUN pip install --no-cache-dir \
    torch \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir sentence-transformers

# ── Слой 2: остальные зависимости приложения
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Слой 3: исходный код (меняется чаще всего — в конце)
COPY app/ ./app/
COPY scripts/ ./scripts/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
