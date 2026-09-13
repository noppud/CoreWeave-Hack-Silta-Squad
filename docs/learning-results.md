# Live learning evidence

| Part | Result | Evidence |
|---|---|---|
| A: original soft jaw | Verified 384.860 → 211.037 s, 45.2% lower estimated machining time | `runs/learning-soft-jaw-a5/manifest.json` |
| B: changed slot sizes and depth | Verified 205.345 s; different geometry, not directly comparable to A | `runs/learning-part-b2/manifest.json` |
| C | Learned B check rejected candidate 2 before simulation in 51 ms; repaired candidate awaits verification after Mac lock | `runs/learning-part-c2/manifest.json` |
| D-J | Queued; paused while Mac is locked | `runs/learning-ten-part-test/progress.json` |

A's judge saved a ramp-feed optimization lesson to `learning/cad_cam.md`; B's first CAM plan explicitly applied the applicable tool preset. The source collision failure taught a fixture-parallel endpoint check. B's stock-conformity failure taught an outer-side intrusion check. Both are in `learning/checks.py`; the second was applied during B's running job.

Diagnostic replays: the first check rejects the actual failed A candidate in 24 ms while allowing its verified repair; the second rejects the actual failed B candidate in 41 ms while allowing its verified repair. These are observed examples, not comprehensive evaluations. No Weave promotion gates are enabled.

A required several CAD/CAM repairs and UI recoveries; B also needed an export-dialog recovery. Those failures and unknown results remain in the run logs. A completed recovery run does not erase them or imply the original run was uninterrupted.

All passes include completed Fusion internal CAM machine checks plus bidirectional finished-stock mesh comparison against fixed CAD, within the recorded tolerance. This does not certify posted-NC execution or cutting physics. Times are Fusion API estimates; UI statistics differ and are retained separately. Videos are not being recorded yet.

Weave calls:
- [A verified optimization](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a098a9-7350-7b4b-adb4-e5d9c997f8c4)
- [A learned fixture check](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a098ad-3518-7fff-a815-21cc0b3585e2)
- [B generation, failure and learned check](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a098ae-dab2-7f63-b230-31e73a08ceca)
- [B verified final plan](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a098b7-8d4b-7489-a092-3859fb7adccd)

Part C provides direct cross-part check-learning evidence: the check written after B's stock-conformity failure rejected C's candidate-0002 before Fusion simulation, in 0.05127 seconds. Candidate-0003 passed the updated checks, but the Mac locked before its simulation results could be collected. The batch is paused, with the saved document and resume script recorded in `runs/learning-ten-part-test/progress.json`.

A source-execution contract defect also appeared in C: generated code defined a Fusion add-in `run(context)` without calling it. The prompt now states module execution explicitly, and a completed source with no solid bodies goes through the existing source-repair path. Forty-six focused agent/export tests pass.
