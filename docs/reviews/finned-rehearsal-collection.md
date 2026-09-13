# Finned rehearsal: collection remains unresolved

September 13, 2026. This is an operational collection issue, not evidence that the
repaired CAM passes manufacturing verification.

| Retained job | Observed outcome |
| --- | --- |
| `runs/stage-finned10-r2/manifest.json` | Candidate1 completed machine verification with28 collision errors. Astra repaired CAM; candidate2 then reported zero machine Issues at100%, but stock-regeneration completion was not observed. Job incomplete. |
| `runs/stage-finned10-r2-recovery1/manifest.json` | Reused the accepted target/retained CAM and separate shadow learning. Zero machine Issues; stock-completion gate timed out. Job incomplete/unknown. |
| `runs/stage-finned10-r2-recovery2/manifest.json` | Fresh recovery again reported zero machine Issues; stock-completion gate timed out. Job incomplete/unknown. |

The first candidate's recorded Issues include Fixture+Cutter, Stock+Holder,
Fixture+Shaft, Fixture+Holder and Stock+Shaft, associated with the indexed−Y blind
obround. Its305.462361-second estimate belongs to a failed candidate.

For the repaired candidate and recoveries, the exact retained issue is
`TimeoutError: Fusion stock regeneration completion was not observed`.
Their `completed` flag is false, machining time is null, and finished-stock
comparison is absent. Zero machine Issues does not supply the missing stock verdict.

Root later observed apparently finished stock during a cold recovery, but the
runner did not observe the required regeneration-completion sequence. Visual
appearance alone did not override the gate. A temporary progress-API probe exposed
only its own empty progress state; it is not a supported substitute for Fusion's
stock-generation completion. The production completion condition was not weakened,
and no manufacturing pass was manufactured.

The earlier `runs/stage-finned10-r1/manifest.json` remains a completed historical
rehearsal with three passes and separate recorded playbacks. It does not establish
that this fresh run succeeded. All recoveries retain their source chain in
`workspace/resume-provenance.json` and use shadow learning; they are neither new
campaign parts nor fresh timed presentations.

The provisional next live input is UMC08 octagon, `stage-octagon08-r1`. Its fresh
rehearsal is pending; do not describe it as validated until the actual manifest and
presentation receipt show a completed pass and observed playback motion.
