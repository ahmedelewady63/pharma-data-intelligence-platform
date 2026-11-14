SHELL := /bin/sh
PYTHON ?= python

.PHONY: setup format lint test

setup:
	$(PYTHON) -m pip install -r requirements-dev.txt
	pre-commit install

format:
	ruff check --fix .
	ruff format .

lint:
	ruff check .
	ruff format --check .

test:
	pytest
