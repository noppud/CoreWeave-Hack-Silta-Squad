Add a standalone programmatic CNC simulator and live CAM workspace under `cnc_simulator/`, separate from the existing Fusion integration. A reviewed PDF produces a frozen target, Astra CAM strategies, compiled movements, deterministic checks, stock-removal verification, timing-only feedback, and persisted memory.

The engine exports stock meshes and movement-driven replay on the downloaded UMC-750 geometry. It supports fixed-axis milling and indexed 3+2, flat-end tools, and conservative geometry gates. Numerical uncertainty fails the gate; geometry and collision checks never become a weighted optimization score. The timing estimate assumes constant feeds/rapids and explicit dwell, index and tool-change durations.

A fresh installation starts with empty memory; existing history is preserved. A reproducible three-part complexity runner is included, with explicit memory seeding and CAD-only preparation. The live optimizer retains the best verified plan across worse candidates and recoverable compiler errors. The viewer frames final stock and restores the cutter when replay resumes.

Validation and limits:

- Default standalone test suite run in a fresh Python 3.12 dependency environment; 78 passed in 91.46 seconds on the isolated current branch, including midpoint-only indexing-collision coverage and terminal disconnect/partial-state regressions. Result: publication-tests.xml.
- Fresh extracted live run reviewed in-browser: Bearing Pocket, 80.745 → 25.852 estimated seconds, memory 0 → 1, target unchanged, playback inspected. This is a reliability run, not a controlled learning comparison.
- The live UI resolves adjacent assets through an editable install, as documented in HANDOFF.md. Astra account access is required for PDF/CAM model calls; the core simulator requires no model or account.
- Demo geometry uses 1 mm cells and 3 mm tolerance. No simultaneous five-axis verification, controller-accurate timing, cutting-force certification, or arbitrary PDF reconstruction.
- The four legacy VF2/Fusion provenance tests are not included in this standalone addition; they remain in the original working project and require parent-repository assets. All engine/loop tests are included.
- Recorded benchmark studies, private live histories, Weave credentials, competition film, and local virtual environments are excluded. No claim of general cross-part memory-driven speed improvement.

This is a local review branch. It has not been pushed, merged, or submitted to the event.
