.PHONY: setup check doctor models trace demo notebook

setup:
	python3 scripts/bootstrap.py
	uv sync --locked

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest

doctor:
	uv run python -m silta.setup

models:
	uv run python -m silta.setup --models

trace:
	uv run python -m silta.setup --trace

demo:
	uv run python -m silta

# Optional sponsor notebook editor; no notebook or GPU allocation is created automatically.
notebook:
	uv run --with marimo marimo edit
