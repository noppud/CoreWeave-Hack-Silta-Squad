.PHONY: setup check doctor models trace demo notebook app evals eval-offline

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

# The product: the workbench application. No credentials required.
app:
	uv run marimo run notebooks/workbench.py

# The experiment surface: policy comparison, holdout result and sponsor evidence.
evals:
	uv run marimo run notebooks/evaluations.py

# Offline policy comparison over the frozen corpus; no network, no spend.
eval-offline:
	uv run python -m silta.evaluation

# Optional sponsor notebook editor; no notebook or GPU allocation is created automatically.
notebook:
	uv run --with marimo marimo edit

# Two browser slides and the reproducible three-minute presenter notebook.
present:
	bash scripts/start_presenter.sh
