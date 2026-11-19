.PHONY: setup lint format test
# On Windows run these commands directly in a terminal if `make` is not installed.

setup:
	python -m pip install -r requirements-dev.txt
	pre-commit install

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .

test:
	pytest -q
