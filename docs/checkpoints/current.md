# Checkpoint — Silta CNC implementation

Time: September 12, 2026, afternoon Pacific. Baseline commit: `81c2cc4` (working tree not yet
committed). Session: one lead implementation agent plus bounded subagents, one writer per file.

## Last accepted work

T01–T08 of [the implementation plan](../implementation.md) are implemented and verified, including
the live Cloud Run release and its remote acceptance run. F1–F4 of the follow-up specification are
implemented behind flags. 118 tests pass.

## Working user flow

`make app` → `marimo run notebooks/workbench.py` serves the workbench. The demonstration job starts
by itself on page load: the supplied drawing is read, its specification confirmed and frozen, and
the naive shop recipe is planned, checked, compiled and simulated. No clicks are required to see
the loop; operator controls to change policy, starting point, candidate count and deadline sit
below it.

## Checks run and exact outcomes

| Check | Result |
| --- | --- |
| `uv run ruff check .` / `ruff format --check .` | pass |
| CAD against the independent analytic oracle | volume 85 519.971 mm³ vs 85 519.974 mm³; bbox 80×60×20; STEP reimport matches |
| Three-attempt demonstration loop | `tool_cutting_reach` → `simulation_collision` (clamp_front, segment s0005) → passed |
| Simulated cut of the passing plan | residual 0.0 mm, gouge 0.0 mm, all 5 features at removed_fraction 1.0, 0.22 s at a 0.5 mm grid |
| `uv run python -m silta.evaluation --holdout` | development 8/8 both policies, holdout 4/4 both policies, 0 false accepts, 0 false rejects, 1 simulation saved by policy-v1 |
| Browser walkthrough at 1600×1000 | all seven sections render, 0 console errors, replay canvas is three.js r160 |

## Defects found and fixed during this session

1. **Drill-tip profile sign.** The simulator cut the drill cone upside down, so the tip removed
   material *above* the tool tip. Every drill reported a stock collision on approach. Fixed; the
   tip is now the lowest point and the cone rises to full diameter at the periphery.
2. **Post-collision metrics were reported as failures.** A run that stopped at the first collision
   also emitted `simulation_residual_stock` and four `simulation_feature_coverage` failures, which
   were never measured. That is false evidence handed to the planner. Those checks now return
   `unknown` with an explicit message instead.
3. **`path_no_rapid_through_stock` false positive.** A vertical retract out of a pocket was treated
   as travelling laterally through material. Only lateral motion below the stock top can tunnel.
4. **`path_fixture_envelope` version 1 was wrong** — the defect the boundary fixtures exist to
   catch. It tested the *holder's* radius against the *tool tip's* height, so a valid vertical
   retract 9.85 mm from a clamp was rejected as 23 mm below it. The simulator, which models each
   part at its own height, said pass. Version 2 tests each tool part at its own radius and its own
   offset above the tip, reusing the simulator's own tool model so the two cannot disagree.
5. **Boundary fixture arithmetic.** `dev_08_boundary_reach_exact` used 1.57 mm for the 118° drill
   point contribution; the correct value is 3/tan(59°) = 1.8025818570826808 mm, so the tool was
   genuinely 0.233 mm short and the checker was right to reject it. The fixture was corrected, not
   the checker.
6. **`ProcessPlan.fingerprint` omitted execution-relevant fields** (feed, spindle, peck depth,
   setup assignment), so two plans with different cycle times shared an identity and a genuinely
   new candidate could be mistaken for a repeat. Named in
   [the follow-up spec](../followups/touko-loop-refactor.md) §6; now fixed, versioned `fp2`, and
   insensitive to cosmetic renaming.
7. **Viewer used three.js's default Y-up** against Z-up engineering coordinates, so the stock
   rendered standing on its edge. Camera up vector, elevation and ground plane corrected.
8. **Widget asset routing.** `viewer.js` fetched `./three.min.js` relatively, which marimo 404s.
   The vendored bundle is now inlined into the widget module, so judging depends on no CDN and no
   host-specific asset route.

## Evidence paths

- `policies/aria-recommendation-001.md` — the promotion record, with the ARIA gate marked unmet.
- `docs/evidence/improvement-001.md` — scrubbed submission summary.
- `fixtures/development/`, `fixtures/holdout/` — 8 + 4 frozen cases, split before tuning.
- `fixtures/demo/` — synthetic drawing, undimensioned variant, analytic oracle.
- `notebooks/evaluations.py` — policy comparison, holdout, convergence, telemetry status.

## Remaining defects and external gates

| Item | Owner | State |
| --- | --- | --- |
| W&B API key | human | **not set.** No live inference, no Weave trace, no W&B run. The app runs deterministically and says so. |
| W&B inference credit grant | human | unconfirmed; the form has not been submitted from this workspace. |
| ARIA team project + Smart features | human | unverified. No ARIA conversation has occurred and none is claimed. |
| Cloud Run release | lead | **done** — see the live release table below. |
| Follow-up loop (supervisor, playbook, check learning) | lead | F1–F4 of `docs/followups/touko-loop-refactor.md` implemented behind `supervised_loop_enabled` (default off) and `check_learning`. F5–F7 not started. |
| Google Fonts | — | the display typeface is fetched from fonts.googleapis.com. It degrades to a local monospace stack if the venue blocks it; nothing functional depends on it. |

## Live release

| Field | Value |
| --- | --- |
| URL | https://silta-1020247549062.us-central1.run.app |
| Revision | `silta-00006-w9q` |
| Image digest | `sha256:ff2c8b6e5569ca71159d1d36c9a217c9268d2729e54b4f3e9c676ee2aad6ed28` |
| Region / project | us-central1 / silta-hack |
| Artifacts | `gs://silta-hack-silta-artifacts` |

Remote acceptance, run against the deployed revision rather than localhost:

| Check | Result |
| --- | --- |
| Public HTTPS without a Google account | pass |
| `/health` | HTTP 200 |
| No third-party code host (Three.js is inlined, not fetched from a CDN) | pass, all scripts same-origin |
| WebSocket upgrade and first kernel frame | pass, 1 960 bytes received |
| No API key in any response or header | pass |
| marimo editor routes refused | pass, 3/3 |
| Full loop on the deployed revision | pass — reach failure, clamp collision, then a passing plan |
| Durable artifacts survive the process | pass — manifests, STEP, STL, trajectories and events in Cloud Storage |
| Two concurrent sessions isolated | pass — distinct session and job IDs, no overlap |

To make the service publicly reachable, the organisation's
`iam.allowedPolicyMemberDomains` constraint was overridden **for the `silta-hack`
project only**, with the user's explicit approval. Roll it back with:

```sh
gcloud org-policies delete iam.allowedPolicyMemberDomains --project=silta-hack
```

## Defects found and fixed after the first release

9. **Viewer round-tripped the whole scene on every interaction.** `playhead`,
   `selected_segment` and `camera_state` were written back to the kernel, and a traitlet
   write re-uploads the entire model — including the megabyte-scale `scene` payload. Over
   a real network this produced "Failed to update model value / Failed to fetch" on pause,
   scrub and orbit. Nothing in Python read those values, so the writes were removed and
   time and camera are now strictly browser-owned.
10. **`google-cloud-storage` was missing from the dependencies**, so the first deployed
    revision could not write durable artifacts and every section after the run failed to
    render. It is now a declared dependency.
11. **The container had no `.git`**, so the build label read "uncommit". The commit is now
    stamped into the image as `SILTA_COMMIT`.
12. **Three smoke checks asserted the wrong contract** — HTML from a JSON health endpoint,
    a Three.js asset URL that no longer exists now the bundle is inlined, and a WebSocket
    guess based on status codes. They were corrected, and the WebSocket check is now a real
    handshake that reads a frame.

## Defects found by the comprehensive verification pass

Four adversarial verification agents were run against the controller/service failure paths,
the geometry engine, the learning subsystem and the live deployment. Findings, all
independently reproduced before acting:

13. **CadQuery string selector broke only in the deployed service.** `silta/cad.py` used
    `.edges("|Z")`, which CadQuery parses with pyparsing. pyparsing infers a parse action's
    arity by introspecting a traceback, and built first inside a worker thread under marimo's
    instrumented execution it settled on the wrong arity: the live job died with
    `atom_callback() missing 1 required positional argument: 'res'` while the identical image
    succeeded on the main thread. Replaced with the selector object the string compiles to.
    A regression test now builds CAD from a worker thread.
14. **A legal pocket crashed the CAD builder.** `.rect(...).fillet(r)` raises
    `BRep_API: command not done` when the corner radius reaches half the narrow width — a
    legal slot shape that the domain validator accepts. The profile is now drawn analytically
    from lines and arcs, which covers the whole legal range and matches the closed-form area
    to machine precision. This also removes the last OCCT fillet dependency.
15. **One corrupt object crashed all memory recall.** `LearningMemory._read_collection` called
    `json.loads` unguarded, so a single truncated blob raised `JSONDecodeError` and took the
    whole namespace down. On the live service the public demo shares one namespace across
    every visitor, so one bad write would have broken every later job. Unreadable and
    schema-invalid entries are now skipped and recorded in `LearningMemory.skipped`.
16. **The per-call timeout was hardcoded.** `silta/planner.py` passed `timeout_s=45.0`
    regardless of `Budget.call_timeout_s`, so a configured budget was ignored and one slow
    provider call could consume the job deadline. The budget is now threaded through.
17. **A mutable class attribute was shared by every controller.** `JobController.outcomes`
    was declared at class level, so every controller instance ever constructed shared one
    dictionary: job outcomes accumulated across sessions and the dict grew for the lifetime of
    the process. Now per-instance.
18. **The job deadline was only checked between attempts.** A slow planning call could run past
    the deadline and the job then reported "no feasible plan was found" rather than the truth.
    The deadline is now also checked immediately after a planner call, and the message says the
    deadline was hit while planning.
19. **A hostile upload filename kept its parent-directory hops.** `Path(name).name` does not
    treat a backslash as a separator on POSIX, so a Windows-style name survived into the
    display field that reaches manifests, setup sheets and logs. Storage keys were never
    affected — they are always generated ids — but the label is now sanitised too.
20. **A provider failure downgraded silently.** When a configured provider failed, the planner
    fell back to the deterministic planner and the run looked healthy. The attempt record was
    honest (`plan_source="deterministic_planner"`), but nothing announced the downgrade.
    `PlanResult.fallback_reason` now carries why, and the controller emits a
    `planner_fallback` event naming the cause.

Reported but NOT defects, after independent checking:

- The deployment verification initially concluded the live service failed its acceptance gate
  because of a `google-cloud-storage` ImportError. Those log lines predated the fix by several
  revisions; the current revision writes manifests to Cloud Storage normally.
- `dev_08_boundary_reach_exact` was reported as a false rejection. The fixture's own arithmetic
  was wrong (1.57 mm instead of 3/tan(59 deg) = 1.8025818570826808 mm for the drill point), so
  the tool really was 0.233 mm short and the checker was right.

## Verification status after the comprehensive pass

`uv run pytest -q` -> **223 passed, 1 skipped, 5 xfailed**. `uv run ruff check .` and
`ruff format --check .` clean. Test files now cover:

| Area | File | What it pins |
| --- | --- | --- |
| Geometry oracles | `tests/test_geometry_oracles.py` | 42 tests against hand-calculated closed-form values, never against the builder's own output |
| Controller/service failure paths | `tests/test_robustness.py`, `tests/test_service.py` | cancellation, budgets, deadlines, idempotency, session isolation, provider failure modes, artifact integrity |
| Learning subsystem | `tests/test_learning_integration.py` | memory scoping and re-verification, playbook applicability, check promotion, supervised selection |
| Existing units | the rest of `tests/` | domain, cad, checks, toolpaths, simulation, controller, planner, storage, evaluation, presentation |

The 5 remaining xfails are deliberate. Four pin a stricter "a provider failure must fail the
job" contract that we chose NOT to implement, because the product must keep working with no
inference configured — the downgrade is instead made visible through the `planner_fallback`
event. The fifth covers an invalid specification that the domain validator rejects before the
job starts. Their reasons say so explicitly rather than claiming an unfixed defect.

## Not yet deployed

The fixes numbered 14-19 below are in the working tree and verified locally, but the running
Cloud Run revision predates them. The live service still works — it was verified end to end
after the CAD selector fix — but it is running the earlier image. Rebuild and redeploy with
`bash scripts/deploy.sh` (or a `gcloud builds submit` plus `gcloud run deploy` by digest) to
bring the deployment level with the tree.

## Next smallest task

Add a W&B API key so live inference, Weave traces and W&B run metrics can be verified,
then open ARIA against a real baseline batch.

No secrets appear in this checkpoint. A successful local command, a pushed commit, a visible trace
and a submitted project are four distinct states; only the first is currently true.
