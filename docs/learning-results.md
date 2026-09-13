# Four-part learning test

User stopped the batch at four parts. All four have verified final plans; Parts E-J were not run.

| Part | Estimated machining time | Final run |
|---|---:|---|
| A | 211.037 s, improved from 384.860 s | `runs/learning-soft-jaw-a5` |
| B | 205.345 s | `runs/learning-part-b2` |
| C | 211.850 s, improved from 228.182 s | `runs/learning-part-c5` |
| D | 208.573 s | `runs/learning-part-d1` |

Every final plan passed completed Fusion internal CAM machine verification and bidirectional finished-stock comparison against fixed CAD, within 0.127 mm. All four final Weave calls were read back successfully. Exact files, document identities, versions and receipts are in `runs/four-part-learning-summary.json`.

## Learning that was actually observed

1. **Prompt learning:** A's judge measured a 45.2% machining-time reduction from a bounded ramp-feed change and saved reusable guidance. B's first CAM plan used the applicable imported ramp-feed preset.
2. **Check learning:** A's collision failure produced a fixture-parallel endpoint check. A replay rejected the failed plan in 24 ms and allowed its verified repair.
3. **Transfer to another part:** B's stock-conformity failure produced a finished-side intrusion check, applied during B's running job. It subsequently rejected C's candidate-0002 **before simulation in 51 ms**. This is the strongest direct cross-part learning example.
4. **Further prompt learning:** C's judge measured a 7.2% reduction from relaxing a ramp stepdown cap within the supplied angle/feed bounds and saved that lesson. D used the resulting ramp-planning approach and finished after one simulation, following a generation repair.

The active learned state is still exactly `learning/cad_cam.md` and `learning/checks.py`. Weave records traces; no evaluation/promotion gate is enabled.

## Limits of the result

These are different drawings, so their final times are not a controlled learning curve. We have demonstrated actual updates, reuse and a prevented simulation failure; we have not established that every later part is faster. Empty narrow-pocket generation still required repair on multiple parts. UI/source-integration recoveries were necessary, so the entire four-part experiment was not uninterrupted.

Passes cover internal CAM simulation and bounded stock-mesh conformity, not physical cutting or posted-NC certification. UI timing and API timing differ; the objective stayed unchanged. Videos have not been recorded yet.

## Weave evidence

- [A verified optimization](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a098a9-7350-7b4b-adb4-e5d9c997f8c4)
- [A learned fixture check](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a098ad-3518-7fff-a815-21cc0b3585e2)
- [B failure and learned check](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a098ae-dab2-7f63-b230-31e73a08ceca)
- [B verified final plan](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a098b7-8d4b-7489-a092-3859fb7adccd)
- [C verified improvement and prompt update](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a098c9-7ed1-7b60-81e5-6f877aebfda8)
- [D complete run](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a098cc-666f-73b3-9c6a-10e12875fe32)
