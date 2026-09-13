# Repeated cold/warm CAM comparison

New model proposals and simulations on two existing benchmark parts, frozen memory from actuator only. No within-study updates. Selected-part transfer experiment, not unseen-part or physical validation.

Frozen memory contains only the actuator episode. Both arms receive the same reference result, fixed target, compiler, and verifier. No study results update memory. Order alternates within pairs; runs are not seeded or blinded.

| Part | Repeat | Cold seconds | Warm seconds | Warm minus cold |
|---|---:|---:|---:|---:|
| 03-bearing-block | 1 | 124.164 | 124.164 | 0.000 |
| 03-bearing-block | 2 | 125.525 | 130.221 | 4.696 |
| 03-bearing-block | 3 | 126.797 | 130.221 | 3.424 |
| 04-trunnion-cage | 1 | 360.003 | 196.773 | -163.230 |
| 04-trunnion-cage | 2 | 197.775 | 196.773 | -1.002 |
| 04-trunnion-cage | 3 | 197.885 | 196.773 | -1.112 |

6/6 paired passes. Warm faster: 3; cold faster: 2; ties: 1.

These selected repeated comparisons test the effect of this frozen memory on these parts. They do not establish generalization to unseen CAD or physical machining. Timing is the fixed simulator estimate. Failures and inference errors remain in result.json and never receive a passing time score.
