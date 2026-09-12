#!/bin/bash
# Wrapper script to run make_demo_drawing.py with correct PYTHONPATH
PYTHONPATH="$(cd "$(dirname "$0")/.." && pwd):$PYTHONPATH" uv run python "$(dirname "$0")/make_demo_drawing.py" "$@"
