# Full local demo setup for Konsta

Download the [full demo materials release](https://github.com/noppud/CoreWeave-Hack-Silta-Squad/releases/tag/demo-materials-2026-09-13). The large files are GitHub release assets, not Git LFS pointers. A normal clone includes the pitch videos; restoring the release adds the complete retained `runs/`, `output/` and `versions/` folder trees, including historical submissions, raw recordings, STEP/STL/Fusion models, NC, drawings, screenshots and learning evidence. Additional CAD archives from local private working folders are included at their original paths.

Credentials, private sessions, temporary connection information, raw process `.log` files, bytecode caches and active replay sessions are excluded. The manifest lists exclusions from the public artifact folders. No software environments or personal authentication are copied. The snapshot preserves original file bytes and paths; it does not modify Touko's running checkout. New work after the snapshot is not included automatically.

## Restore into a fresh clone

Requires Git, Python 3.11+, uv, and about 40 GB free disk space including the downloaded archives. With GitHub CLI:

```sh
git clone https://github.com/noppud/CoreWeave-Hack-Silta-Squad.git
cd CoreWeave-Hack-Silta-Squad
gh release download demo-materials-2026-09-13 --dir demo-downloads
python3 scripts/demo/restore_materials.py demo-downloads
uv sync --locked
uv run python scripts/demo/recorded_workbench.py
```

Alternatively, download every numbered ZIP and `demo-materials-manifest.json` from the release page into `demo-downloads`, then run the last three commands. Each numbered ZIP is independently extractable, but download all of them for the full snapshot. The restore script verifies archive and individual file SHA-256 hashes and refuses to overwrite different existing files. Use a fresh clone, not an active working folder.

Open **http://127.0.0.1:8768**. The part library, 3D models, recorded machining/finished-stock videos, run history, learning examples and source downloads use restored files. The launcher maps Touko's original absolute root to this checkout in memory, preserving the evidence hashes on disk. It starts in review-only mode.

## Present the pitch

In a second terminal at the repository root:

```sh
python3 -m http.server 8080 --bind 127.0.0.1
```

Open **http://127.0.0.1:8080/demo/pitch-app/SILTA%20Pitch%20Deck.dc.html**. Navigate with arrow keys or the sidebar; start recordings with their play controls. The 27-part timeline is an explicitly scripted illustration. React/Babel, D3 and fonts still require internet. See the [pitch instructions](../demo/pitch-app/README.md) and [evidence map](../demo/pitch-app/evidence/README.md).

## Actual live Fusion

Recorded playback and the 3D library do not require Fusion. Fresh CAD/CAM generation, the staged upload/live-Fusion replay and live camera view require a configured local Autodesk Fusion installation, matching machine library/cloud documents, the bridge, and your own authenticated agent/sponsor accounts. Importing an F3D alone does not establish the machine association. Follow [Fusion setup](../fusion/README.md), [configuration relocation](../config/README.md#relocating-a-checkout), and [live connection instructions](live-fusion-connection.md). The release supplies the materials; it does not transfer Touko's authenticated desktop or guarantee a fresh live manufacturing run on another machine.
