pretty:
	poetry install --no-root
	poetry run ruff format *.py
	poetry run ruff check --fix *.py
	poetry run ruff format *.py

lint:
	poetry install --no-root
	poetry run ruff check *.py
	poetry run ruff format --check *.py
