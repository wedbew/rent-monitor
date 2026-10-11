# One image for the API and the workers (blueprint §4.3). Built from the uv workspace lockfile, run as a non-root user.
FROM python:3.12-slim-bookworm AS build
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never PIP_NO_CACHE_DIR=1
RUN pip install --no-cache-dir uv==0.11.14
WORKDIR /app
# Dependencies first (cache-friendly), then the source.
COPY pyproject.toml uv.lock ./
COPY packages packages
COPY services services
RUN uv sync --frozen --no-dev --no-editable --all-packages

FROM python:3.12-slim-bookworm
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --system --uid 10001 --create-home app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY alembic.ini ./
COPY migrations migrations
COPY scripts scripts
USER app
EXPOSE 8000
CMD ["uvicorn", "rm_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
