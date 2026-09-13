# Sponsor evidence and outer development loop

## Organizer criteria, verified against current public sources

The [organizer listing](https://luma.com/coreweavehacks) names Best Loop Design, Best Use of Weave ($1,000), and Best Use of ARIA ($1,000). It emphasizes repeated reasoning/action, finding mistakes, observation, evaluation, tracking and documenting improvements. Submission is Sunday at13:00. The listing explicitly mentions Best Loop winners on9/13. It does not supply numeric judging weights. The saved handbook summary in `docs/hackathon.md` contains stale June schedule wording; use the current organizer listing for schedule confirmation.

For Best Loop, show the actual failure, repair, learned applicability rule, and next-part preflight rejection. For Weave, show paired evaluations and new actual Fusion traces with review evidence. For ARIA, the necessary evidence is an actual ARIA analysis that leads to a concrete tested development change. Merely adding an ARIA label is not use.

## What is actual now

`output/sponsors/sponsor-review.json` contains a retained server snapshot of30 recent root calls and both finalized check evaluation calls. Recent calls include the original new Fusion campaign job and resumed recovery jobs. Server state is preserved separately from local campaign state.

`scripts/demo/sponsor_review.py --publish-feedback` adds deterministic custom review feedback to new Fusion job traces and reads the feedback back. The review distinguishes incomplete collection, verified best candidate, and false completed status. This is custom trace monitoring through Weave's SDK, **not the native Weave Signals product or an LLM monitor**. `output/sponsors/monitor-feedback.json` retains publication receipts and exact findings. The script is a one-shot observation, not a background service.

```sh
hsec exec --only COREWEAVE_WANDB_API_KEY -- .venv/bin/python scripts/demo/sponsor_review.py --publish-feedback
```

The check evaluation evidence remains in `output/evaluation/learning-evaluation.json`. Its publication/readback receipts are retained; this document audit did not make new server calls.

## ARIA access and product boundary

The actual ARIA request and final response are complete, not pending. The team
used the authenticated project UI; retained evidence identifies project-scoped
gpt-5.5. This was ARIA itself, not a call to the separate W&B Inference product.
No selectable model inventory was observed, so no “best available model” claim is
made. The final response and implemented change are detailed below.

Native programmatic Weave scoring is also actual: `output/sponsors/fusion-native-scores.json`
has `status=published_and_read_back`, finalized score calls and root-feedback IDs.
It explicitly records `native_agents_signals=false` and zero scorer model calls.
The separate `fusion-native-scores-preview.json` remains an older local preview;
use the published receipt for evidence. None of this claims native Signals or an
LLM monitor. The scorer snapshot predates the latest UMC12 run; coverage of newer
jobs requires their own matching readback receipts.

## Actual ARIA analysis and implemented revision

The actual ARIA final response is retained in `output/sponsors/aria-response.md`, with identity and validation in `aria-review.json`. ARIA inspected the exact Fusion roots, child verification/check calls and custom feedback, then explicitly used project-scoped **gpt-5.5** for synthesis. It identified four distinct operational readiness/document-binding failures and recommended a bounded readiness gate before verification.

The implemented adaptation is `NativeFusionReader.bring_to_front`: an exact foreground-only focus failure can explicitly activate the Fusion application and set its process frontmost once, then retry focus. Missing-visible-window recovery remains in the existing Mission Control helper. It shares the stock export transport's recovery flag to prevent repeated normalization. Unrelated errors are not replayed. Structured preflight evidence is written locally and attached to raised exceptions so the existing verifier returns unknown/incomplete rather than manufacturing failure.

Existing pinned-document validation stays authoritative. Display controls are not required before launch because they exist after launching simulation. No new model call, CAM parameter change, or additional runtime agent was added.

Validation:16 tests passed across `tests/test_native_reader.py` and `tests/test_fixed_verifier.py`; this includes controlled focus failure/recovery, failed retry, no duplicate restoration and unrelated-error behavior. **The full live unready/clean paired Fusion test proposed by ARIA has not yet run.** The accurate claim is actual ARIA diagnosis → implemented revision → unit verification, plus the narrow live focus recovery below; full-job causal effectiveness is not isolated. ARIA's proposed judge paragraph used past tense before implementation and must not be treated as proof of a successful live pair.

## First live observation after the ARIA-informed change

`demo-umc-umc-03-recovery2` records successful foreground normalization in **3.108 s** after `Fusion lost foreground access; export stopped`; the readiness receipt has `status=ready` and `recovery_attempted=true`. A separate clean focus-only probe recorded readiness in **1.482 s** with no recovery. Exact receipt paths/hashes are retained in `aria-review.json`.

The downstream recovery2 job nevertheless ended **incomplete / verification unknown** because stock export found two visible Accuracy controls. This establishes the narrow live focus-recovery behavior, not complete machining verification, a controlled paired benchmark, or an end-to-end reliability improvement.

UMC03 recovery3 subsequently recorded a full passed verification for candidate1 at **466.793213 s** estimated machining time. This followed a separate native OCR row-bounds type correction (`CGFloat` versus `Double`) that removed duplicate Accuracy controls. That OCR correction was not ARIA-authored. The honest chain is observed ARIA-informed focus recovery, a further independent integration fix, and later completed candidate verification. It does not isolate ARIA's effect on full-job completion. Subsequent CAM optimization is separate from the ARIA contribution.


## Downloadable Fusion evidence

W&B artifact `silta/coreweave-hack-silta-squad/silta-fusion-judge-evidence:v0`
contains the six-completed-drawing snapshot, actual CAD/NC, verification files,
learned sources, evaluations, ARIA evidence and the 114-second film. It is marked
partial. [Upload run](https://wandb.ai/silta/coreweave-hack-silta-squad/runs/43m1kgqx).
Server state is COMMITTED; all 519 remote entries match the local file digests.
Receipt: `output/sponsors/fusion-artifact-receipt.json`. Later campaign results
require a new version; this artifact does not claim ten completed drawings.
