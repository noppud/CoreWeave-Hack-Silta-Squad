"""Verify and restore the GitHub demo release into a fresh checkout."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('downloads', type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.downloads / 'demo-materials-manifest.json').read_text())
    records = {row['path']: row for row in manifest['files']}
    for archive in manifest['archives']:
        path = args.downloads / archive['name']
        if digest(path) != archive['sha256']:
            raise ValueError(f'Archive checksum mismatch: {path}')
        with zipfile.ZipFile(path) as bundle:
            for item in bundle.infolist():
                target = (ROOT / item.filename).resolve()
                if not target.is_relative_to(ROOT) or item.filename not in records:
                    raise ValueError(f'Unexpected archive entry: {item.filename}')
                if target.exists() and digest(target) != records[item.filename]['sha256']:
                    raise ValueError(f'Refusing to overwrite different file: {target}')
    for archive in manifest['archives']:
        with zipfile.ZipFile(args.downloads / archive['name']) as bundle:
            for item in bundle.infolist():
                target = ROOT / item.filename
                if not target.exists():
                    bundle.extract(item, ROOT)
                if digest(target) != records[item.filename]['sha256']:
                    raise ValueError(f'Extracted checksum mismatch: {target}')
        print(f"Verified and restored {archive['name']}", flush=True)
    (ROOT / 'demo-materials-origin.json').write_text(json.dumps({
        'original_root': manifest['original_root'],
        'snapshot_started_at': manifest['snapshot_started_at'],
    }, indent=2) + '\n')
    print(f'Restored and verified {len(records)} files. Original evidence bytes preserved.')


if __name__ == '__main__':
    main()
