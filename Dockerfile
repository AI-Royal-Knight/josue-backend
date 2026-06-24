FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# Set uv to create the virtual environment outside of /app to avoid being overwritten by volume mounts
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"

# Sync dependencies to create a virtual environment inside /opt/venv
RUN uv sync --frozen --no-dev

# Activate the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Copy the rest of the application
COPY . .

EXPOSE 8000

# Default command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
