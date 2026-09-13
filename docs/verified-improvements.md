# Within-part verified CAM improvements

Refresh the source report, then generate the six-part chart and separate manually
nominated cage comparison:

```sh
.venv/bin/python scripts/demo/learning_transfer_report.py
.venv/bin/python scripts/demo/plot_verified_improvements.py --parts UMC04 UMC05 UMC06 UMC08 UMC09 UMC12
.venv/bin/python scripts/demo/plot_verified_improvements.py --parts UMC11 --output output/evaluation/cage-manual-retest
```

The main chart selects first and best valid CAM for six completed indexed parts.
The separate cage chart prominently identifies the **operator-nominated retained
CAM retest**, 4242.119344 → 2357.727194 seconds (44.42%). It is not an autonomous
improvement or new learning. Its provenance is checked against the exact candidate
nomination sidecar, not inferred from a faster time.

Each PNG/SVG has a JSON receipt. The generator reads actual verification events,
checks retained evidence hashes and requires matching drawing, input digest,
target digest and recorded verifier version within each pair. Collection-invalidated
runs are rejected. Invalid UMC08 candidate1 is excluded. UMC06 uses its completed
recovery2 matching-v5 pair,560.900213 → 511.208189 seconds (8.86%); candidate5
needed a recorded one-time operator Issues-panel reopen. UMC12's three valid
candidates improve944.089570 → 908.965929 seconds (3.72%).

UMC03 now completed, but the report's broad historical pair crosses verifier
versions and is excluded from this chart. Its fresh v7 pair is438.955225 →
433.128113 seconds (1.33%). Do not combine old and new verifier values into a
controlled comparison.

Receipts pin the source report, manifests, candidate identities, evidence,
generator and images. Matching recorded verifier identities do not establish
frozen historical implementation bytes or uninterrupted autonomy. Times are Fusion
estimates under configured assumptions, not physical machine measurements.
Differences across drawings do not demonstrate learning causality. Reusable-check
learning evidence remains the earlier three-axis experiment; the indexed campaign
shows existing planning-guidance use and verified CAM optimization.
