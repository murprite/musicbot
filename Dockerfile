# ---------- BUILDER ----------
FROM python:3.13-slim AS builder

ENV PYTHONUNBUFFERED=1
ENV POETRY_VIRTUALENVS_CREATE=false

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        nodejs \
        npm \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install poetry

COPY pyproject.toml poetry.lock* ./

RUN poetry install --no-interaction --no-ansi --no-root

# ---------- RUNTIME ----------
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Устанавливаем runtime зависимости
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g deno
# Копируем python пакеты
COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=builder /usr/local/bin /usr/local/bin

# Копируем проект
COPY . .

CMD ["python", "main.py"]