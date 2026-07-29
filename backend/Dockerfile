FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
RUN mkdir -p app \
    && touch app/__init__.py \
    && pip install --no-cache-dir . \
    && rm -rf /app/app

COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
