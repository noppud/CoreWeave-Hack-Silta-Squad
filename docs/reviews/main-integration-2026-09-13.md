# Fusion and presentation integration into main

Prepared September 13, 2026 in an isolated worktree from remote main `38136d1`.

Merged the prepared Fusion release `34ffc02` and the latest presentation branch
`a238d06`, retaining their history and all pre-existing main files. Restored
`docs/loop.md` from main rather than carrying the release branch deletion.
The original active checkout, its local changes, runs and recordings were not altered.

Included the newer Fusion control center, live gateway, public preview source,
UI files and pinned configuration inputs. The viewer now serves its included
MIT-licensed Three.js dependency and the shared presentation without requiring
`cnc_simulator/`. That standalone simulator and bulk generated output are outside
this integration. Curated pitch media and small drawing inputs are included.

Reconciled presentation checks with the approved 27-part timeline and seven learned
checks. Applied repository Python formatting to implementation and tests; exact
learned-source evidence snapshots retain their original bytes and are explicitly
excluded from Ruff. Captured upstream machine-library files also retain their bytes.

Validation: 584 Python tests passed, one test requiring undistributed local Fusion
evidence skipped, and seven upstream Weave/Pydantic deprecation warnings. Ruff lint
and formatting checks, locked dependency sync, CLI help, and the presentation's
pacing/geometry/event checks passed. The viewer packaging test serves the UI,
reference presentation and all four Three.js files from this isolated checkout.
No fresh Fusion machining or live capture was started for this integration.

The final source scan found no matches for the checked credential/private-key
patterns, no deleted main files, and no file above 100 MiB. The largest included
file is the curated pitch movie at 17,823,489 bytes. Existing main changes were
reviewed: the starter entry point now delegates to the CNC CLI, and README,
planning/submission documents, build commands and dependency metadata describe
that application. Prior content remains available through the retained Git history.
