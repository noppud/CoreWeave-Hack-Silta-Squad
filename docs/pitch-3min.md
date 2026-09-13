# SILTA: three-minute pitch

Six slides, 180 seconds. Open `make slides` before presenting. This version explains
the agreed architecture while the implementation is still being built. Slide 5 is a
planned walkthrough, not a claim of completed execution. Replace its narration with
observations once a real run is available.

## 1. A machining planner that learns from failure (0:00–0:20)

We’re building Silta, an agent that turns a part drawing into a verified machining
plan. The idea is simple: give the agent feedback from tests and simulation, and let
it improve the way it makes the part.

## 2. The part is only half the problem (0:20–0:45)

The drawing tells us what the finished part should look like. It doesn’t tell us the
best way to make it with a particular machine and set of tools. The planning choices
still matter: which tool to use, how to move it, and how long the job will take.
We keep the target part fixed and improve the process around it.

## 3. The loop (0:45–1:25)

Here’s the loop we’re building. The agent takes the drawing and a set of planning
instructions, then generates machine instructions. First, we run cheap tests. If a
test fails, the agent gets the reason and tries again. If the tests pass, we run a
machining simulation. A failed simulation goes back to the agent too. A passing
simulation goes to a judge, together with the machining time. The judge either
accepts the plan or sends back instructions for another revision.

## 4. The feedback becomes instructions (1:25–1:55)

The learning happens in that feedback. A failure tells the agent what to repair.
If simulation exposes something the tests missed, we can propose and validate a
new test. Even a passing plan can improve: the judge uses the simulation and time
to update the planning instructions. The next attempt starts with what we learned
from the previous one.

## 5. One part through the whole loop (1:55–2:40)

Our demo follows one part through that entire process. We’ll show the first machine
instructions, the feedback that rejects them, and the revision that follows. Then
we’ll rerun verification on the revised plan. The important comparison is the same
part, with the same constraints, before and after the feedback. We want to show
exactly what changed and how the machining time compares. That gives the judge a
concrete basis for deciding whether to keep improving or accept the plan.

[When available, use the rest of this slot to show the actual run and its trace.
If it is still unavailable, keep the wording above and advance without claiming a result.]

## 6. The same part. A better machining plan. (2:40–3:00)

Our goal is a verified plan with less machining time. The drawing stays the same.
The machine instructions get better through tests, simulation, and the judge’s
feedback. That’s Silta: an agent that can use the consequences of its last attempt
to make a better next one.

## Before the final presentation

- Replace the planned walkthrough with an observed run if it is ready. Only state
  results that the run actually demonstrates.
- Keep any measured improvement tied to the same part and machine constraints.
- Add the verified Weave trace and sponsor role when the implementation is connected.
- The deck does not claim model-weight training or physical machining validation.
- Rehearse once aloud. At 2:40, move to the closing slide.
