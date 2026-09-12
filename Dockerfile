FROM python:3.12-slim

# Copy the uv binary from official Astral uv image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation and unbuffered logs
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

# Install essential system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency configuration files
COPY pyproject.toml uv.lock ./

# Install project dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Place virtual environment binaries in PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code and application files
COPY src/ ./src/
COPY main.py ./

# Create persistent storage directory for SQLite checkpoints
RUN mkdir -p /app/data

# Expose FastAPI service port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

# Start the application via uvicorn
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
