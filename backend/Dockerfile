FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/aegis/.local/bin:${PATH}"

WORKDIR /app

RUN addgroup --system aegis && adduser --system --ingroup aegis --home /home/aegis aegis

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN chown -R aegis:aegis /app /home/aegis
USER aegis

EXPOSE 8000

# Deliberately a single uvicorn worker process (no --workers N, no gunicorn).
# The app owns in-process/stateful runtime components (the event bus and the
# digital twin simulation state) that are not shared across processes. Forking
# multiple worker processes within this one replica would create independent,
# diverging copies of that state and break correctness (events/state seen by one
# worker would be invisible to requests served by another). Horizontal scaling is
# handled at the Container Apps replica boundary instead, which is intentionally
# capped at maxReplicas=1 for this phase for the same reason. Moving beyond a
# single process/replica requires redesigning that state to be shared/external
# (e.g. externalizing the event bus and twin state to Redis/Postgres) — out of
# scope for Phase 6 and tracked as a known limitation.
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]

