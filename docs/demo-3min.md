# SILTA CAD — six-slide pitch

[Open the deck](slides.html). Arrow keys navigate; Home returns to the cover.

## Order and timing

| Slide | Time | Purpose |
| --- | --- | --- |
| 1. Intro | 10 s | Name the product and the manufacturing decision. |
| 2. Problem | 15 s | A shop needs to turn a new drawing into a feasible machining plan. |
| 3. Interactive demo | 75 s | Show a failed attempt, feedback, revision and what carries to the next part. |
| 4. Videos | 40 s | Show actual CAD/CAM generation and simulation in the product. |
| 5. Architecture / Weave | 20 s | Explain what Astra, Fusion and Weave do. |
| 6. ARIA | 20 s | Explain the concrete advice that helped the team build. |

The official handbook was reread live during this revision. It gives three minutes and no more than one or two explanatory slides, with emphasis on the demo. The six-slide review deck follows Joel’s requested order. For strict stage compliance, use the intro and combined architecture/sponsor explanation as the two explanatory slides; deliver the problem and ARIA context verbally around the demo and videos. Keep the full deck for preparation and Q&A.

## Grading alignment

Source: [official participant handbook](https://wandbai.notion.site/CoreWeave-Hacks-Participant-Handbook-3c9e2f5c7ef380eab21ecdde12620caf). The handbook still has stale June schedule headings; this review uses its grading and presentation rules, not those dates.

| Criterion | Evidence in this pitch |
| --- | --- |
| Best Loop | Slide 3: failure → new code test; slow plan → speed instruction; revised CAM tested again. Show an actual improvement when the recording is ready. |
| Creativity | Slides 3 and 5: planning, checking and judging roles cooperate through concrete feedback. |
| Utility | Slide 2: one manufacturing problem, stated briefly. |
| Technical execution | Slide 4: actual product recordings. Slide 5: understandable application/Fusion/Weave boundaries. |
| Sponsor usage | Slides 5–6: trace evidence and the specific ARIA recommendation, implementation and result. |

Most Production-Ready is a later award, two weeks after the event. Do not spend the three-minute presentation listing speculative production features. The handbook also requires W&B use, a code repository judges can inspect, disclosure of prior work, team eligibility and a completed submission. Those are submission tasks, not more pitch slides.

## Speaking notes

**Intro:** “SILTA CAD helps a shop work out how to manufacture a new part, before committing to the job.”

**Problem:** “The shop receives a drawing. It needs a process that works with its machines and tools, and an estimate of the machining time.”

**Interactive demo:** “The learned lists start empty. Simulation failures add distinct checks at the test gate. When the judge thinks a valid plan can be faster, its feedback updates the CAM-writing LLM’s speed instructions. Revised CAM returns through checks and simulation. Relevant lessons persist for later parts.” The separate animated timeline is illustrative; do not present its chart values as real manufacturing measurements.

**Videos:** Show the product working. Keep the first clip focused on input and CAD/CAM generation, the second on simulation and revision. Placeholder areas remain until the recordings are ready.

**Architecture:** The current source has an Astra-driven application, Fusion simulation, persisted code checks and CAM instructions, and Weave tracing. Weave records evidence; it does not run the manufacturing loop or approve learned updates. The final Weave walkthrough is explicitly unfinished per Joel’s latest instruction. Add a real trace and show one attempt’s input, feedback and revision when ready.

**ARIA:** The new `docs/aria-loop-review.md` records a review of the current source and a concrete repository integration proposal. ARIA helped us learn Weave, challenged immediate shared learning, and proposed comparing old and new checks and prompts on the same unseen parts. It mapped that work to policy versions, trace events and existing paired evaluation code. The next step is one check replay and one prompt comparison in Weave. This remains a proposal: no runtime changes or new manufacturing experiments were performed by the review. Explain the contribution without displaying the transcript. ARIA is not the runtime speed judge.

## Source discipline

Use the active source branch designated by Joel. Current review: [toukoversion](https://github.com/noppud/CoreWeave-Hack-Silta-Squad/tree/toukoversion), including `README.md`, `silta/cnc/tracing.py`, `learning/cad_cam.md` and `learning/checks.py`. Old branch results, former fixture comparisons and recipe-reuse results are excluded from this deck. Nothing has been archived or deleted from GitHub.

The current branch README describes a real Fusion run but also says cross-part learning still needs demonstration. Do not treat software tests using adapter doubles as manufacturing evidence. Older ARIA onboarding/design advice is retained context, not proof of a newer implemented recommendation.

## Ready for final media

- `agent-loop-slot` on slide 3: interactive product/loop demo.
- `product-video-1-slot` and `product-video-2-slot` on slide 4: product recordings.
- Slide 5: replace the pending footer with verified Weave evidence after tomorrow’s integration.
- Slide 6: the current ARIA recommendation is summarized. Add its implemented effect only after matching it to a commit and measured result.

The original team photo remains embedded in the cover. All six slides use the same light background and Arial typography.

## Build

    python scripts/build_demo_slides.py

The build requires Python Markdown and embeds `demo/assets/team.jpeg`. It generates `demo/slides.html` and `demo/guide.html` without importing the product or old evaluation data.
