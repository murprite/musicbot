# ---------- BUILDER ----------
FROM python:3.13-slim AS builder

ENV PYTHONUNBUFFERED=1
ENV POETRY_VIRTUALENVS_CREATE=false

WORKDIR /build

# Устанавливаем системные зависимости только в builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        nodejs \
        npm \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*
# Обновляем pip
RUN pip install --upgrade pip
# Устанавливаем Poetry
RUN pip install poetry

# Копируем файлы зависимостей
COPY pyproject.toml poetry.lock* ./

# Устанавливаем зависимости
RUN poetry install --no-interaction --no-ansi --no-root

# ---------- RUNTIME ----------
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
# Копируем Python зависимости
COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=builder /usr/local/bin /usr/local/bin

# Копируем ffmpeg бинарник
COPY --from=builder /usr/bin/ffmpeg /usr/bin/ffmpeg

# Копируем node runtime (для yt-dlp)
COPY --from=builder /usr/bin/node /usr/bin/node
COPY --from=builder /usr/bin/npm /usr/bin/npm

# Копируем проект
COPY . .

# Команда запуска
CMD ["python", "main.py"]
