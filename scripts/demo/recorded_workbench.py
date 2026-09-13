"""Run restored recordings with original absolute paths mapped in memory only."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from silta.cnc import control_center as app


def main():
    origin = json.loads((ROOT / 'demo-materials-origin.json').read_text())['original_root']
    original_reader = app.read_json
    original_path = app.Catalog.path

    def relocate(value):
        if isinstance(value, str):
            return value.replace(origin + '/', str(ROOT) + '/')
        if isinstance(value, list):
            return [relocate(item) for item in value]
        if isinstance(value, dict):
            return {key: relocate(item) for key, item in value.items()}
        return value

    def read_json(path, default=None):
        return relocate(original_reader(path, default))

    def catalog_path(self, value):
        return original_path(self, relocate(str(value)))

    app.read_json = read_json
    app.Catalog.path = catalog_path
    # Archival review never starts a new manufacturing job.
    if '--review-only' not in sys.argv:
        sys.argv.append('--review-only')
    app.main()


if __name__ == '__main__':
    main()
