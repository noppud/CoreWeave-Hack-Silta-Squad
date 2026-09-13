# Memory persistence audit

This audits saved bytes, commit receipts, and the actual first CAM request. Version counters alone do not establish learning.

| Job | Memory | Persistence + CAM input | Extra per-job copy |
| --- | --- | --- | --- |
| 14003f2fb9fd / Bearing Pocket | 5 → 6 | verified | historical copy absent |
| 3dea6444a879 / Instrument Pocket | 6 → 7 | verified | historical copy absent |
| 3ef2fc936a92 / Bearing Pocket | 7 → 8 | verified | historical copy absent |
| 02de8c83d5bd / Bearing Pocket | 8 → 9 | verified | historical copy absent |
| a1b399e521ac / Instrument Pocket | 9 → 10 | verified | historical copy absent |
| 056866dee37c / Instrument Pocket | 10 → 11 | verified | historical copy absent |
| a2ff5d26d533 / Bearing Pocket | 11 → 12 | verified | historical copy absent |
| 3f1703103c1f / Bearing Pocket | 12 → 13 | verified | verified |
| 99006bbab905 / Instrument Pocket | 13 → 14 | verified | verified |

Persistence and actual CAM-input checks: 9/9. Consecutive links verified: 8/8. All artifact copies present: 2/9. Missing historical artifacts: 7. Failed comparisons: 0.

This is not a memory-transfer experiment. Use the separate 24-plan study to assess speed effects.
