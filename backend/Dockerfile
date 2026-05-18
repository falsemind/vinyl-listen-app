FROM python:3.13.4-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libzbar0 \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/poetry.lock /app/backend/

ARG POETRY_EXTRAS=""
ARG POETRY_VERSION=2.3.3

RUN pip install --upgrade pip "poetry==$POETRY_VERSION" \
    && poetry config virtualenvs.create false \
    && if [ -n "$POETRY_EXTRAS" ]; then \
        poetry install --only main --extras "$POETRY_EXTRAS" --no-root --no-interaction --no-ansi; \
    else \
        poetry install --only main --no-root --no-interaction --no-ansi; \
    fi

COPY backend /app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
