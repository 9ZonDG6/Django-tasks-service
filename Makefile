.PHONY: server check
server:
	uv run python manage.py runserver 8001
check:
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest
	uv run python manage.py check
	uv run python manage.py makemigrations --check --dry-run
