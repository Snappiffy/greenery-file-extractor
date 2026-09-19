FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    EXTRACTOR_SHARED_SECRET=change-me-change-me-change-me-32ch \
    FETCH_ALLOWED_HOSTS=localhost \
    ENVIRONMENT=production \
    OCR_ENABLED=false
WORKDIR /app

# System dependencies. tesseract only when WITH_OCR=true.
ARG WITH_OCR=false
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 \
 && if [ "$WITH_OCR" = "true" ]; then \
      apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng; \
    fi \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Cacheable dependency layer
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=3).status==200 else 1)"

CMD ["uv", "run", "uvicorn", "extractor.api.app:app", \
     "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
