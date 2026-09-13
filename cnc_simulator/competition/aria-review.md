# Actual ARIA review — September 12, 2026

Read from the completed ARIA sidebar in team project silta/coreweave-hack-silta-squad. ARIA queried only programmatic-cam-five-part-evidence:tcBnFBfbWDcP7tEXblahHZCKjnfa3yHeaBlg1WVrEM0 and its four evaluation cohorts. This is a summary of the observed response, not a simulated ARIA conversation.

## Findings

- Best geometry pass rate 5/5 versus reference 4/5.
- Four passing pairs: 2655.74 s reference versus 690.67 s best, 73.99% reduction; 61.5–78.8% individual reductions.
- Failed manifold reference excluded from timing comparison. Recovery to 158.98 s is a feasibility result.
- Four cold/warm pairs: 2 warm faster and 2 slower; 603.30 s warm versus 589.85 s cold. No causal memory benefit established.
- Passing high-stepover and cleanup-disabled examples refute blanket rules.

## Recommended next experiment

Hold each best strategy fixed and ablate junction_cleanup with stepover around observed failure boundaries. Manifold: 0.708, 0.75, 0.95; cage: 0.75, 0.83, 0.95. Include actuator, bearing and sleeve as negative controls. Geometry/collision gates stay fixed; only passing machining times compare.

## Recommended signals

Geometry pass and issue certainty; paired time improvement only when both pass; cold/warm differences with sign counts and strategy changes; check-trigger precision and false rejection; target, source, dataset and simulator digests plus tolerance and memory versions. Uncertain geometry is not a pass or proof of a physical defect. Version changes define new cohorts.

## Sandbox diagnosis

Normal W&B project is readable. Project-not-found at sandbox creation does not prove the normal project is absent or the organization is disabled. Test minimal organization-scoped creation. ARIA suggested legacy wandb.sandbox.Sandbox.run; installed SDK deprecates that in favor of cwsandbox. We will use installed SDK's equivalent auth without entity/project headers, retain error stage, and never claim host subprocess isolation.

## Selected response

The exact-failure audit was already started independently before ARIA completed; do not attribute that experiment to its recommendation. Next execute cleanup ablation on the two observed risk geometries, retain valid controls from the fresh audit, and report actual results back to ARIA. No unrestricted generated rule is promoted.
