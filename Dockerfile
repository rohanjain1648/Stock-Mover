# Stock Mover API (FastAPI + in-process engine). Render: runtime docker, plan free.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
# tzdata: Asia/Kolkata for the 07:00 scheduler (slim images may lack /usr/share/zoneinfo)
RUN pip install --no-cache-dir -r requirements.txt tzdata

COPY engine engine
COPY data data
COPY contracts contracts
COPY backend backend

# run unprivileged; the app writes backend/state.db and outputs/ (ephemeral on Render free)
RUN useradd --create-home --uid 10001 app && mkdir -p /app/outputs && chown -R app /app
USER app

EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
