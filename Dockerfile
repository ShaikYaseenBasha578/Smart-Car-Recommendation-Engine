# One image, two entry points: the Flask site (gunicorn app:app) and the FastAPI service (uvicorn api_service.main:app).
# Build:  docker build -t carrec .
# Stage 1 installs the Python packages into a virtualenv; stage 2 copies only that venv and the runtime files.

FROM python:3.12.7-slim-bookworm AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt requirements-api.txt ./
RUN pip install -r requirements.txt -r requirements-api.txt

FROM python:3.12.7-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/opt/venv/bin:$PATH" PORT=8000
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# Runtime files only (the .dockerignore also keeps the knowledge base, backups, eval results and secrets out of the context).
COPY app.py utils.py ranking_engine.py ./
COPY services ./services
COPY ml_parser ./ml_parser
COPY api_service ./api_service
COPY templates ./templates
COPY static ./static
COPY project_pages ./project_pages
COPY data ./data
COPY car_recommendation_assets ./car_recommendation_assets
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=4)" || exit 1
# Default: the API service. The Flask site overrides the command (see docker-compose.yml).
CMD ["sh", "-c", "exec uvicorn api_service.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
