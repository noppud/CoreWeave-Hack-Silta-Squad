"""Create local configuration once without overwriting a teammate's settings."""

from pathlib import Path

root = Path(__file__).resolve().parents[1]
try:
    with (root / ".env").open("x") as target:
        target.write((root / ".env.example").read_text())
    (root / ".env").chmod(0o600)
    print("Created .env. Add your W&B API key, then run make models to choose a model.")
except FileExistsError:
    print("Kept existing .env unchanged.")
