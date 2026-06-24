FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# Sync dependencies to create a virtual environment inside /app/.venv
RUN uv sync --frozen --no-dev

# Activate the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Copy the rest of the application
COPY . .

EXPOSE 8000

# Default command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
