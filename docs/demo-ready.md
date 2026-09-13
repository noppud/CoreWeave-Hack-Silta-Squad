# Start here for the Fusion demo

The system has completed 13 distinct campaign drawings and a separate finned-part rehearsal. The more complex examples include a windowed cage and a ribbed clevis, with actual Fusion machining recordings and verified finished stock.

## Show these

1. **[114-second film](../output/presentation/silta-loop-demo.mp4):** recorded machining, the core loop, learning evidence, Weave evaluation, ARIA, and the cage/clevis reveal. The film is silent, ready for your narration.
2. **[Two slides](../output/pdf/silta-demo-slides.pdf):** explain the loop and the historical learned-check transfer. The [gallery](../output/presentation/part-gallery.variety.png) shows the distinct complex geometries.
3. **[Live command and spoken runbook](demo-runbook.md#preferred-retained-octagon-live-command):** keep Fusion visible; start a fresh job from the prepared octagon. Show the raw terminal, code, checks and actual simulation. CAD/CAM preparation is disclosed as having happened earlier.

Full complex-part machining recordings: [windowed cage](../output/video/umc11-close-capture-r3/machine-playback.mp4) and [ribbed clevis](../output/video/umc12-close-capture/machine-playback.mp4). These are longer raw takes; use the short film for the timed pitch.

## What the evidence supports

- A historical simulation failure became a check that caught the repeated mistake on a later part in **51 ms**. The [Weave replay](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a0997e-c591-7d3f-984c-4d661ab3d124) catches both retained invalid cases and accepts all four valid ones. These are six historical cases, not an unseen-parts benchmark.
- The completed [octagon rehearsal](reviews/live-rehearsal.md) verified four candidates and played each back with automatic cleanup. Its final plan is **6.14% faster** than the first verified plan on the same fixed CAD. The supervisor stopped when the next change produced no gain.
- The clevis improved **3.72%** across three verified plans. The cage's separate **44.42%** improvement followed a manually nominated earlier plan; do not present that nomination as autonomous learning.
- The campaign reuses planning guidance across parts. The rehearsal used separate learning copies and did not add a new check or prompt change.

These are Fusion CAM estimates using one cutter and indexed **3+2** machining. Keep physical machining and simultaneous five-axis claims out of the pitch.

## Ready to hand off

Source is in [draft PR #2](https://github.com/noppud/CoreWeave-Hack-Silta-Squad/pull/2), with **552 tests passing**. The local [evidence index](../output/submission/silta-fusion-evidence-20260913T105008Z/index.html) includes the completed campaign, failed attempts, learning sources, verification, film and evaluation receipts.

The [final W&B evidence artifact](https://wandb.ai/silta/coreweave-hack-silta-squad/runs/cuto4ljg) is committed, with all 2588 file digests checked against the local bundle.

The event submission form, teammate surveys/roster and judge access to the private W&B project still need confirmation. The portable package can supply the evidence without changing project visibility. See [submission details](submission.md).
