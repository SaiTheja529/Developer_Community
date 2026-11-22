FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PROJECT_ENVIRONMENT=/app/.venv PATH="/app/.venv/bin:$PATH"
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev
COPY . .
RUN useradd -m app && chown -R app /app
USER app
EXPOSE 8080
CMD ["./scripts/entrypoint.sh"]
