.PHONY: setup check doctor models trace demo notebook slides slides-edit slides-export

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

# Presentation commands need no credentials or agent service.
SLIDES_PORT ?= 2740

slides:
	uv run --group slides marimo run notebooks/slides.py --host 127.0.0.1 --port $(SLIDES_PORT)

slides-edit:
	uv run --group slides marimo edit notebooks/slides.py --host 127.0.0.1 --port $(SLIDES_PORT)

slides-export:
	mkdir -p artifacts
	uv run --group slides marimo export html notebooks/slides.py --no-include-code -o artifacts/slides.html -f
