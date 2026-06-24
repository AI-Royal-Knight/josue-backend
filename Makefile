.PHONY: run migrate makemigrations shell dbshell superuser collectstatic test lint format check install

# Run development server
run:
	uv run python manage.py runserver

# Create migrations
mm:
	uv run python manage.py makemigrations

# Apply migrations
migrate:
	uv run python manage.py migrate

# Create and apply migrations
mig:
	uv run python manage.py makemigrations
	uv run python manage.py migrate

# Django shell
shell:
	uv run python manage.py shell

# Database shell
dbshell:
	uv run python manage.py dbshell

# Create superuser
superuser:
	uv run python manage.py createsuperuser

# Collect static files
static:
	uv run python manage.py collectstatic --noinput

# Run tests
test:
	uv run python manage.py test

# Check project
check:
	uv run python manage.py check

# Format code
format:
	uv run black .
	uv run isort .

# Lint code
lint:
	uv run ruff check .

# Install dependencies
install:
	uv sync

# Generate requirements.txt if needed
freeze:
	uv export --format requirements-txt > requirements.txt
