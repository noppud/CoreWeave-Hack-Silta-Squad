.PHONY: setup check doctor init notebook

setup:
	uv sync --locked

check:
	uv run ruff check silta tests checks notebooks/cnc_app.py
	uv run ruff format --check silta/cnc tests/test_cnc*.py tests/test_sandbox.py tests/test_fusion_bridge.py
	uv run pytest

doctor:
	uv run python -m silta doctor --fusion

init:
	uv run python -m silta init

notebook:
	uv run marimo run notebooks/cnc_app.py --host 127.0.0.1 --port 2720
