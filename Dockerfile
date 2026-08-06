FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# Place the virtual environment outside /app so volume mounts don't overwrite it
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"

# Add venv to PATH so 'python' resolves to the venv Python (e.g. when docker exec-ing)
ENV PATH="/opt/venv/bin:$PATH"

# Sync all dependencies using uv (cloudinary, gunicorn, whitenoise, etc.)
RUN uv sync --frozen --no-dev

# Copy the application code
COPY . .

# Copy & make the entrypoint executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
