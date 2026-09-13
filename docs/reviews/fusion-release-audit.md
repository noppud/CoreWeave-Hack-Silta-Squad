# Fusion release audit

Snapshot: 2026-09-12 PDT / 2026-09-13 UTC. Branch `toukoversion`. Read-only audit; no staging, commits, publishing, Fusion activity or runtime edits. Working files may continue changing after this snapshot.

## Remote integration prerequisite

Parent fetched the current remote during this audit. Local HEAD `0afc2ec` is ten commits behind `origin/toukoversion` at `6b746c0`. The remote already contains the older Fusion snapshot plus Joel's demo, slides, project context and ARIA review. The lists below were classified relative to local HEAD, not as a ready-to-apply remote diff. Some files marked new locally (including learning-part PDFs) are already tracked remotely.

Use a separate release worktree based on the fresh remote, then reconcile/copy the allowlisted Fusion implementation there. Do not overwrite, reset, mass-merge or force-push the active working tree. Preserve remote `AGENTS.md`, `demo/**`, `docs/project-context.md`, `docs/aria-loop-review.md`, `docs/demo-3min.md`, `scripts/build_demo_slides.py` and `scripts/pitch_template.html`. Reconcile README by section so these entry points survive. The remote agent guidance and project-context document were read; their loop/evidence boundaries agree with the current explicit user direction.

There are two separately recorded ARIA engagements: Joel's source/product/evaluation architecture review in remote `docs/aria-loop-review.md`, and the local Fusion session-readiness trace review in `docs/sponsor-evidence.md`. Preserve both with their own inputs, outputs and implementation status. Do not substitute one narrative for the other, or describe the proposed evaluation-gate migration as currently active.

## Release decision

The Fusion implementation can form a coherent source commit separate from `cnc_simulator/`. The exact proposed file list is below. A fresh clone is **not currently an independently runnable retained demo**: source input paths, machine-library/cloud binding and historical evidence remain local. This is a packaging/setup gap, not evidence that the locally completed Fusion runs failed.

Concrete fixes before describing the repository as a reproducible judge demo:

1. **Curate output; never add the directory wholesale.** `output/` is not ignored. It currently contains 971,513,102 bytes, including a 374,418,382-byte raw wide video and ZIPs of 105,015,041 and 92,546,127 bytes. The largest raw movie and largest ZIP exceed GitHub's ordinary 100 MiB per-file limit. There are also duplicated unpacked bundles. Keep the small pinned drawing PDFs in source; publish the selected film/evidence through the intended artifact route. Add output/tmp/session ignore rules with explicit PDF exceptions, or use the exact allowlist. `.git/` is already about 962 MiB; this audit did not rewrite or diagnose history.
2. **Document/bootstrap another checkout and Fusion account.** All 20 inspected job configurations pin host-absolute paths. Their referenced files exist locally, but the new PDF, UMC machine and pedestal assets listed below are untracked. `config/README.md` acknowledges relocation but supplies no executable relocation step. The UMC config also points to a particular Fusion cloud `data_file_id` and `user://Silta UMC750 demo.mch`; `fusion/prepare_cam_setup.py` reads that library URL. Copying local `.mch`/`.f3d` bytes does not establish this library/cloud link for a judge. Provide a machine import/link setup procedure and path relocation that preserves artifact hashes; rerun input verification after relocation. Do not alter active job inputs while they are in use.
3. **Give the judge a portable evidence entry point.** `runs/` is intentionally ignored; the notebook and reporting scripts read retained manifests and artifacts there. `scripts/demo/verify_demo.py` additionally requires `.private/five-axis/video-wide-2/result.json`. A fresh clone cannot run the README's acceptance command against those unavailable files. `scripts/demo/package_evidence.py` already builds a normalized, hash-indexed evidence bundle and omits private files and large Fusion archives; it is an evidence viewer bundle, not a reconstruction of the executable run tree. Link a deliberately selected bundle/film and describe the empty-state behavior, or provide a public receipt/import path. Preserve original versus normalized hashes instead of pretending rewritten records are byte-identical originals.
4. **Fix contradictory current-status text.** README says “ARIA is deferred,” while retained response and submission/runbook describe a completed ARIA review and implemented bounded recovery. `scripts/demo/sponsor_review.py` still writes native monitors/signals `not_configured` and an ARIA-blocked state; these conflict with its shared project and newer evidence. Do not rerun it as the canonical current sponsor report unchanged. `docs/sponsor-evidence.md` also retains an in-progress paragraph above its completed-review section; timestamp or remove the superseded status. Keep native programmatic `FusionOutcomeScorer` results distinct from native Agents Signals and from the custom simulator's non-Astra shared monitor. `config/README.md` still says the post has never been used live, and `docs/showpiece-part.md` begins “Prepared, not run”; date those preparation snapshots or point to current campaign evidence.
5. **Do not promise enforced held-out evaluation.** UMC07 is labeled held out in input metadata and docs, but `scripts/demo/run_fusion_campaign.py` accepts any passed config and always uses the shared learning directory. It neither rejects the held-out split nor disables learning. Reserving UMC07 by invocation is sufficient for the current training campaign; claiming an enforced held-out evaluation is not. Before running it as a held-out evaluation, use a genuinely frozen/no-update path or add the explicit guard. This audit did not run any held-out part.

## Boundaries and findings

- All 35 currently modified tracked files were examined by scope. Thirty-four belong in the Fusion/shared-repo change; the exception is generated `notebooks/__marimo__/session/cnc_app.py.json`. No tracked runtime change was identified as custom-simulator-only. This is a content assessment, not a claim about author ownership.
- `cnc_simulator/` is the separate implementation and is entirely outside this commit. `docs/reviews/2026-09-12-fastest-path.md` is a cross-implementation architecture review; `docs/reviews/2026-09-12-simulator-profile.json` measures that custom simulator. Exclude both from Fusion evidence. `docs/reviews/2026-09-12-fusion-timings.json` is optional historical Fusion timing evidence, not needed to execute the demo.
- Root `pyproject.toml`/`uv.lock`, README and submission documentation are shared metadata, but their current changes support the Fusion path. OCCT, libigl, Shapely and mesh dependencies are used by `silta/cnc/stock_comparison.py`; do not remove them as presumed custom-simulator dependencies. `cwsandbox` is pre-existing and does not prove hosted sandbox use. The custom application has separate project files.
- The actual verification boundary is stated accurately in `fusion/README.md`: APIs handle setup/CAM/postprocessing; deterministic macOS native automation collects completed internal-CAM simulation evidence and exports stock. It is not a public headless milling-verification API, posted-NC motion verification or physical cutting validation. Native helper source and stock-comparison code are required additions. No Astra clicking is needed for routine collection.
- `docs/evaluation-contract.md` is explicitly marked inactive. Current default learning directly edits two files; retrospective paired Weave evaluations are real but are not live promotion gates. Do not restore the old gate claim in the release description.
- The current `learning/` files contain learned state, not empty starting checks. Include as a clearly identified campaign snapshot, and document using a new `--learning-directory` for a fresh baseline; `SharedLearning` initializes missing files. Never reset the active files to manufacture a replay.
- PDF generators import ReportLab, which is absent from the root dependency manifest. Their documentation assumes a bundled local Python. Since the exact tiny PDFs are included below, normal jobs need not regenerate them. For portable authoring, document `uv run --with reportlab python ...` (and the other generator commands) instead of a user's runtime path. Film scripts already document the separate `imageio-ffmpeg` dependency route.
- Credential-pattern scan covered 159 changed/new text files up to 2 MB, excluding custom-simulator files, unpacked bundles and tmp. No matches for OpenAI/W&B/GitHub/AWS token formats, private PEM keys, long literal Bearer strings or long secret assignments. This was a bounded text scan, not an audit of binary screenshot/video pixels or all git history. No secret values were printed. Many configs and raw reports contain host/private path references; these are portability/provenance issues, not detected credentials.
- `git diff --check` passed at this snapshot. No full test suite or external integration run was performed by this release audit. Existing recorded validation does not automatically cover edits made after it.

## Exact proposed source commit allowlist

This list deliberately excludes raw output reports/media. It includes the source and the exact small drawing inputs needed by the included configs. Review current documentation contradictions above before staging. The source snapshot is finite; do not replace it with directory-wide staging while other tasks are working.

### Modified tracked Fusion/shared files

```text
README.md
docs/evaluation-contract.md
docs/implementation-plan.md
docs/submission.md
fusion/README.md
fusion/SiltaBridge/operations.py
fusion/cam_documents.py
notebooks/cnc_app.py
prompts/check_writer.md
prompts/supervisor_prompt.md
pyproject.toml
silta/cnc/agents.py
silta/cnc/astra.py
silta/cnc/benchmarks.py
silta/cnc/cli.py
silta/cnc/controller.py
silta/cnc/evaluation.py
silta/cnc/fixed_verifier.py
silta/cnc/fusion_reader.py
silta/cnc/models.py
silta/cnc/simulation_coverage.py
silta/cnc/simulation_report.py
tests/test_cam_documents.py
tests/test_cnc_agents.py
tests/test_cnc_app.py
tests/test_cnc_benchmarks.py
tests/test_cnc_controller.py
tests/test_cnc_datasets.py
tests/test_cnc_evaluation.py
tests/test_fixed_verifier.py
tests/test_fusion_reader.py
tests/test_simulation_coverage.py
tests/test_simulation_report.py
uv.lock
```

### New runtime, demo tooling, learning snapshot and tests

```text
fusion/INDEXED_CAM_API.md
fusion/SiltaBridge/presentation.py
fusion/operation_frames.cps
fusion/operation_frames.py
learning/cad_cam.md
learning/checks.py
scripts/demo/benchmark_geometry_backend.py
scripts/demo/campaign_report.py
scripts/demo/edit_fusion_video.py
scripts/demo/evaluate_learning.py
scripts/demo/learning_transfer_report.py
scripts/demo/live_terminal.py
scripts/demo/package_evidence.py
scripts/demo/part_gallery.py
scripts/demo/prepare_bracket.py
scripts/demo/prepare_fusion_campaign.py
scripts/demo/prepare_showpiece.py
scripts/demo/presentation_build.py
scripts/demo/presentation_film.py
scripts/demo/resume_fusion_job.py
scripts/demo/run_fusion_campaign.py
scripts/demo/score_fusion_runs.py
scripts/demo/sponsor_review.py
scripts/demo/stage_fusion_demo.py
scripts/demo/verify_demo.py
scripts/fusion/native_ui.swift
scripts/fusion/post_operation_frames.py
scripts/fusion/record_part_reveal.py
scripts/fusion/window_video.swift
silta/cnc/learning.py
silta/cnc/native_reader.py
silta/cnc/presentation.py
silta/cnc/simulation_video.py
silta/cnc/stock_comparison.py
silta/cnc/stock_export.py
tests/test_cnc_view.py
tests/test_demo_readiness.py
tests/test_demo_terminal.py
tests/test_demo_weave_scorer.py
tests/test_native_reader.py
tests/test_operation_frames.py
tests/test_post_operation_frames.py
tests/test_presentation_orbit.py
tests/test_simulation_video.py
tests/test_sponsor_review.py
tests/test_stage_fusion_demo.py
tests/test_stock_comparison.py
tests/test_stock_export.py
```

### New Fusion documentation

```text
docs/bracket-part.md
docs/campaign-results.md
docs/demo-campaign.md
docs/demo-evaluation.md
docs/demo-runbook.md
docs/five-axis-demo.md
docs/geometry-performance.md
docs/learning-results.md
docs/learning-transfer.md
docs/showpiece-part.md
docs/simulation-video.md
docs/sponsor-evidence.md
docs/three-hour-demo-plan.md
docs/weave-monitoring-options.md
```

### New input configurations and required machine/drawing assets

```text
config/demo-campaign/manifest.json
config/demo-campaign/umc-02-job.json
config/demo-campaign/umc-03-job.json
config/demo-campaign/umc-04-job.json
config/demo-campaign/umc-05-job.json
config/demo-campaign/umc-06-job.json
config/demo-campaign/umc-07-job.json
config/demo-campaign/umc-08-job.json
config/demo-campaign/umc-09-job.json
config/haas-umc750-linked.mch
config/learning-part-b-job.json
config/learning-part-c-job.json
config/learning-part-d-job.json
config/learning-part-e-job.json
config/learning-part-f-job.json
config/learning-part-g-job.json
config/learning-part-h-job.json
config/learning-part-i-job.json
config/learning-part-j-job.json
config/umc-actuator-job.json
config/umc-actuator-tall-job.json
config/umc-pedestal-direct-g54.f3d
config/umc-tall-pedestal-g54.f3d
output/pdf/demo-campaign/umc-02.pdf
output/pdf/demo-campaign/umc-03.pdf
output/pdf/demo-campaign/umc-04.pdf
output/pdf/demo-campaign/umc-05.pdf
output/pdf/demo-campaign/umc-06.pdf
output/pdf/demo-campaign/umc-07.pdf
output/pdf/demo-campaign/umc-08.pdf
output/pdf/demo-campaign/umc-09.pdf
output/pdf/learning-part-b.pdf
output/pdf/learning-part-c.pdf
output/pdf/learning-part-d.pdf
output/pdf/learning-part-e.pdf
output/pdf/learning-part-f.pdf
output/pdf/learning-part-g.pdf
output/pdf/learning-part-h.pdf
output/pdf/learning-part-i.pdf
output/pdf/learning-part-j.pdf
output/pdf/umc-actuator-housing.pdf
research/five-axis/haas-umc750-reboot.f3d
research/five-axis/haas-umc750-reboot.mch
research/fusion-background-control.md
```

The allowlist contains 140 files with 8,616,966 bytes of working-tree contents (not the eventual git pack delta). Most new asset size is the official UMC simulation geometry, 6,568,341 bytes; the linked machine is 44,730 bytes and tall pedestal 95,105 bytes. These are modest compared with the raw media. Exact `.mch` and `.f3d` provenance should remain documented as external Autodesk/downloaded machine assets versus project-authored fixtures.

## Explicit exclusions and optional evidence

Exclude `cnc_simulator/**`, `tmp/**`, `notebooks/__marimo__/session/cnc_app.py.json`, `.private/**`, `runs/**`, `versions/**`, `output/submission/**`, raw `output/video/**`, intermediate `output/presentation/**`, `output/fusion-workbench.html`, and directory-wide `output/**`. Preserve these locally; exclusion is not deletion.

Unused preparation/provenance assets that are not referenced by the inspected jobs can remain outside the minimal commit: `config/haas-umc750-linked-input.mch`, `config/umc-pedestal-g54.f3d`, `config/_XRef_/umc-pedestal-direct-g54.f3d`, `research/five-axis/catalog.json`, `research/five-axis/machines.js`, `research/five-axis/machines-library.html`, `research/five-axis/haas-umc750-reboot.machine`. The direct pedestal archive itself is included because `config/umc-actuator-job.json` pins it. Verify any additional intended import workflow before deciding it needs the `_XRef_` copy.

Optional judge evidence to publish/curate separately: `output/evaluation/learning-evaluation.json`, `output/evaluation/learning-transfer.json`, `output/evaluation/learning-transfer.md`, `output/evaluation/fusion-campaign.json`, `output/evaluation/fusion-campaign.csv`, `output/sponsors/aria-response.md`, `output/sponsors/aria-review.json`, `output/sponsors/fusion-native-scores.json`, and the chosen presentation film. Several raw JSONs contain absolute/private references. Prefer the bundle's normalized copies plus source hashes; do not commit every duplicated source report just to satisfy links. `output/evaluation/replay-evidence.json` is about420 KB but contains over1,000 host/private references and requires ignored historical artifacts for replay: its presence alone would not make the historical benchmark executable on a clone.

No new permission or approval requirement was inferred. The remaining decisions are file curation, portable setup/evidence delivery and accurate release wording.
