# Questions to rehearse

## What actually improved?

On three frozen complex targets, fixed-reference time totals 4548.57 seconds and selected passing plans total 1250.26 seconds, a 72.5% modeled reduction. That is baseline-to-optimized performance, not proof of memory learning. After the timing judge requested another attempt, the carrier improved 531.038 to 496.788 seconds. The manifold tied. The drum regressed from 444.100 to 450.365 seconds, so the earlier passing plan remained selected. All attempts are retained in `../workspace-complex-three/summary.json`; `iteration-audit.json` checks best retention and target hashes.

## Does memory help on new parts?

The system demonstrably saves memory and supplies it to later CAM requests. Nine live jobs have verified saved-byte and request-input chains. A separate 24-plan study across four geometries did not establish a useful general speed benefit. The supported benefit is narrower: an exact-failure check catches selected repeated invalid plans before repeating full simulation. Do not equate persistence with generalization or model-weight learning.

## Did you manufacture a failure for the demo?

No. The retained manifold reference failed numerical verification. Astra received its issue and revised CAM; the revised plan passed. Later resolution-only testing made one unchanged manifold plan pass at a finer grid, while a cage remained unresolved. This is evidence about numerical verification, not proof of a physical defect or a time improvement caused by refinement.

## What does the judge do?

It receives verified timing history and asks to continue or stop. CAM chooses strategy parameters. Invalid geometry cannot qualify by being faster. In the complex runs, each judge's `guidance_proposal` is null; the retained reason requests improvement or stops when attempts are exhausted. The target geometry does not change.

## What is the simulator actually checking?

It removes bounded stock occupancy along cutter sweeps and checks target gouging, leftover material, configured tool/fixture collisions, noncutting contact, rapid-through-stock and travel limits. Indexing does not remove material. New regression cases have clear start/end poses but a definite collision midway through rotation, including holder-only contact. All eight indexing tests pass.

## Is this a five-axis production simulator?

It is indexed 3+2 on downloaded UMC-750 geometry. It rotates between cuts; it does not perform simultaneous five-axis cutting. The demonstration uses 1 mm cells and 3 mm tolerance. No cutting-force, whole-machine self-collision or controller-accurate timing claim. Actual stock-removal playback is separate from the immutable target, and unresolved numerical cases fail the gate.

## What did Weave and ARIA contribute?

Weave records live execution stages and scored datasets, with completed readback receipts. ARIA reviewed evidence and suggested an experiment. Twelve cleanup/stepover cases were run; they yield only five distinct effective paths. The results support limited manifold cleanup advice, not a universal rule. The independent transfer study stayed negative/mixed. Native Weave Signals are not configured and must not be presented as active.

## What ran in the sandbox?

Frozen exact-failure-check logic, with network denied and no guest credentials. The hosted receipt is `hosted-checks.json`. This was not the complete stock-removal simulator running in the sandbox.

## Can we see a new live run?

Start a reviewed PDF job at the beginning of the demo. The supported drawing intake covers vertical circular/obround blind pockets; the complex showpieces use structured indexed inputs. Use the real job id with `live_terminal.py`. If inference is still pending, show its actual state and clearly identify a completed replay as the fallback. The film is a 116-second edited recording; it is not live execution.

## Can another person run it?

The source archive includes installation instructions, tests, live viewer, downloaded machine assets, complex-part runner and raw terminal observer. Fresh memory starts at version zero; recorded complex results used version fourteen. The isolated current branch passed 78 tests. Public branch publication is still awaiting approval, and judge access/submission are not established by local tests.
