.PHONY: setup check doctor models trace demo notebook app evals eval-offline weave-evals

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

# Publish the frozen corpus to W&B Weave as a real Evaluation, for both policies.
# Needs WANDB_API_KEY. Uses the deterministic planner, so it costs no inference credits.
weave-evals:
	uv run python -m silta.weave_evals --split development
	uv run python -m silta.weave_evals --split holdout

# Offline policy comparison over the frozen corpus; no network, no spend.
eval-offline:
	uv run python -m silta.evaluation

# Optional sponsor notebook editor; no notebook or GPU allocation is created automatically.
notebook:
	uv run --with marimo marimo edit

# Seven interactive marimo slides, pitch guide, backup deck and detail notebooks.
present:
	bash scripts/start_presenter.sh
