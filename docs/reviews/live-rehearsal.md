# Completed retained-octagon rehearsal

`stage-octagon08-r1-recovery1` completed and selected candidate 5. Four fresh
verification passes recorded estimated machining times 1591.867942,1561.445259,
1515.202754 and 1515.202754 seconds for candidates 3–6. The supervisor stopped because
candidate 6 repeated the incumbent's NC/feed/time outcome. Relative to original r1
candidate 1 at 1614.396515s, the same fixed CAD improved **6.144%**.

All four playback receipts record observed tool motion, successful SimulationStop
and restored target display, without cleanup errors. Presentation took 37.74–37.87s
per candidate including setup and cleanup; it is separate from verification and is
not a new machining verdict. The retained source/digest summary is
[stage-octagon-final.json](../../output/evaluation/stage-octagon-final.json).

The recovery started with previously prepared candidate 3 and fixed accepted CAD,
then generated new CAM candidates with collision-free IDs. Initial and final shadow
checks/prompt hashes are identical. This demonstrates verified CAM optimization and
an unattended presentation sequence; it does not demonstrate a new learned check
or fresh unseen-drawing preparation within a three-minute talk.

Original r1 hit its attempt cap and needed operator cleanup after playback failed.
Its receipts remain unchanged. The finned r2 and its recoveries remain incomplete
because the strict stock-collection gate did not establish completion. Neither is
silently relabeled by this successful octagon run.

[Actual Weave recovery trace](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a09a51-6741-753f-ab92-d297767bbc73).
The [final evidence artifact](https://wandb.ai/silta/coreweave-hack-silta-squad/runs/cuto4ljg) is published and read back with matching file digests. Use the [retained-live command](../demo-runbook.md), with a fresh job ID and
new shadow learning directory. It starts fresh verification and a supervisor decision;
any further optimization can exceed the presentation slot. No physical machine or
posted-NC approval is claimed.
