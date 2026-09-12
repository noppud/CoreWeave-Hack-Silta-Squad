# The agentic loop

How Silta CNC's agent works, what it is allowed to change, what counts as feedback, and how
the next attempt is measured. Every number in this document was produced by running the code;
the commands that produce them are given so you can reproduce them.

---

## 1. The idea in one paragraph

A CNC shop receives a part drawing. Someone has to decide *how* to make it: which tool, how
deep per pass, how high to lift the spindle when crossing the clamps. Getting that wrong is
expensive — a short tool cannot reach the bottom of a pocket, and a low traverse destroys a
fixture. Silta turns the drawing into a solid model and a machining recipe, then **measures the
recipe against real geometry**. When a measurement fails, the measurement itself — not a
sentence describing it — goes back to the planner, and the next attempt is measured the same
way. The customer's part never changes; only the process does.

The distinction that makes this a loop rather than a retry: the agent does not get told *"that
didn't work, try again."* It gets told *"the tool's cutting length is 8.0 mm, the feature needs
12.0 mm, here is the tool and the operation."* That is a fact with a repair implied by its own
structure.

---

## 2. What is deterministic and what is a model

This is the most important table in the document. A model's opinion can never turn a failure
green.

| Stage | Who decides | Why |
| --- | --- | --- |
| Read the drawing | **Model** (vision) or typed input | Proposes values; a human confirms them. Unknown stays unknown. |
| Confirm the specification | **Human** | Freezes a revision. Nothing downstream may alter it. |
| Build the solid and export STEP | **Code** | Trusted CadQuery primitives driven by validated JSON. The model never emits code. |
| Propose a machining recipe | **Model** | Bounded JSON DSL only: setups, operations, tools, step parameters, clearance. |
| Check the recipe | **Code** | 28 deterministic checks across four stages. |
| Compile the toolpath | **Code** | Fixed templates. The model never emits motion. |
| Simulate the cut | **Code** | 2.5D stock removal and swept collision against real fixture solids. |
| Decide pass or fail | **Code** | A conjunction of hard conditions. Unknown is not pass. |
| Repair from the failure | **Model** | Reads structured evidence, proposes a new recipe. |
| Select the best candidate | **Code** | Pure, deterministic comparison of verified candidates. |

The model occupies five roles — interpreter, planner, repairer, supervisor, and proposer of new
checks and lessons — and every one of them **proposes**. Nothing it returns is trusted until
deterministic code has measured it. Role labels describe responsibility, not concurrency: one
model fills all five, called serially inside one budget.

---

## 3. The permission boundary

Repair is allowed to change how the part is made. It is not allowed to change the part, or to
move the goalposts.

**A repair may change:** the tool selected for an operation, the order of operations, the setup
assignment, entry strategy, stepdown and stepover, feeds and speeds within machine limits, and
the clearance plane.

**A repair may never:** alter a dimension, material or feature position; invent a tool that is
not in the shop inventory; move or remove a fixture; expand the machine envelope; edit a
threshold; or mark its own result as passing.

These are enforced in code, not in a prompt. The confirmed design is hashed, the shop profile is
hashed, and both hashes are stamped onto every candidate plan by trusted code — the model cannot
set them. Two checks, `design_unchanged` and `shop_unchanged`, compare them on every attempt. A
tool id that is not in `ShopProfile.tools` fails `tool_available` before anything else runs.

Changing the part requires a visible human edit, which creates a new specification revision and
invalidates every artifact derived from the old one.

---

## 4. Loop A — repair inside one job

This is the loop a judge sees on the live page.

```
   confirmed spec ──► CAD build (STEP + mesh)
                          │
                          ▼
        ┌──────────► propose recipe ──► preflight checks ──┐ fail
        │                                     │ pass       │
        │                                     ▼            │
        │                            compile toolpath      │
        │                                     │            │
        │                                     ▼            │
        │                              path checks ────────┤ fail
        │                                     │ pass       │
        │                                     ▼            │
        │                          stock + collision sim ──┤ fail
        │                                     │ pass       │
        │                                     ▼            │
        │                              PASSED              │
        └───── structured failure evidence ◄───────────────┘
```

Checks run in cost order, so the cheapest thing that can reject a recipe rejects it first and no
machine time is spent simulating a plan that was already impossible:

| Stage | Checks | Cost |
| --- | --- | --- |
| `schema` | `design_unchanged`, `shop_unchanged`, `feature_reference` | microseconds |
| `preflight` | `tool_available`, `tool_operation_compatible`, `tool_cutting_reach`, `tool_stickout_clearance`, `pocket_corner_radius`, `pocket_width_fit`, `stepover_bound`, `entry_capability`, `hole_diameter_match`, `drill_point_angle`, `feature_coverage`, `machine_feed_limit`, `machine_spindle_limit`, `workspace_envelope` | microseconds |
| `path` | `path_continuity`, `path_travel_bounds`, `path_no_rapid_through_stock`, `path_fixture_envelope`, `path_compilation` | milliseconds |
| `simulation` | `simulation_collision`, `simulation_residual_stock`, `simulation_gouge`, `simulation_feature_coverage` | ~0.2–0.8 s |

**Feasibility is a conjunction.** A plan passes only when the schema is valid, the design hash is
unchanged, the CAD is valid, *every* blocking check passed, every required feature is covered,
and the simulation succeeded. Unknown or timed-out is not a pass. A low estimated cost never
offsets a hard failure.

### The stopping conditions

The loop always terminates, and it terminates visibly:

- a candidate passes;
- the candidate budget is spent (default 3) → `needs_human_review`;
- the model-call budget is spent (default 6, counting interpretation, planning, repair, schema
  repair and supervision) → `budget_exhausted`;
- the job deadline passes (default 120 s) → `budget_exhausted`;
- the planner proposes a candidate it already proposed → `needs_human_review`;
- the operator cancels → `cancelled`, and **a cancelled job never publishes a success** even if
  an attempt had already passed;
- the input is unsupported or the requirements are unsatisfiable → `needs_human_review`.

A software fault in the builder is a software fault. It is never treated as permission to change
a valid requested shape.

---

## 5. What feedback actually looks like

This is the heart of the design. Every check returns a structured record, not prose:

```json
{
  "check_id": "tool_cutting_reach",
  "check_version": "1",
  "stage": "preflight",
  "status": "fail",
  "severity": "blocking",
  "feature_id": "pocket_1",
  "operation_id": "op_pocket_1",
  "actual": 8.0,
  "required": 12.0,
  "units": "mm",
  "evidence": {"tool_id": "EM6-S", "feature_kind": "pocket_rect_rounded"},
  "repair_hint": "Select an available tool with sufficient cutting reach; preserve the requested depth."
}
```

The planner receives the confirmed specification, the real tool inventory, the compact policy
rules, its own previous candidate, and these records. It does not receive an unbounded chat
history — constraints accumulate as facts, not as transcript.

The simulator's verdict is converted into the *same shape*, so a collision found by stock
simulation is fed back with the same structure as a tool-length mismatch found in microseconds:

```json
{
  "check_id": "simulation_collision",
  "stage": "simulation",
  "status": "fail",
  "severity": "blocking",
  "segment_id": "s0005",
  "operation_id": "op_pocket_1",
  "actual": 0.157,
  "required": 0.0,
  "units": "mm",
  "evidence": {
    "obstacle_id": "clamp_front",
    "obstacle_kind": "fixture",
    "colliding_part": "cutter",
    "tool_z_mm": 5.0
  },
  "repair_hint": "Raise the clearance plane above every fixture the tool traverses, or reorder the motion. Do not move the fixture or change the part."
}
```

**Honesty rule.** When a simulation aborts at its first collision, coverage and residual stock
were never measured — so they are reported as `unknown`, not as failures. An earlier version
reported them as failures, which fed the planner four pieces of evidence about material removal
that no one had measured. Fabricated evidence is worse than no evidence.

---

## 6. A real run, start to finish

Reproduce it by opening the app (`make app` — the job runs on page load), or by driving the
service directly:

```python
import asyncio
from pathlib import Path
from silta.service import SiltaService, RunRequest
from silta.fixtures import DEMO_SHOP, naive_plan, confirmed_demo_spec
from silta.domain import Budget


async def main():
    service = SiltaService(artifact_root=Path("/tmp/silta-trace"))
    request = RunRequest(
        session_id=service.new_session_id(),
        spec=confirmed_demo_spec(),
        shop=DEMO_SHOP,
        policy_version="policy-v0",
        seed_plan=naive_plan(),
        budget=Budget(),
        memory_enabled=False,
    )
    async for event in service.run_job(request):
        print(event.type, event.payload)


asyncio.run(main())
```

The shop has three tools — `EM6-S` (6 mm end mill, 8 mm cutting length), `EM6-L` (6 mm, 18 mm),
and `DR6` (6 mm drill) — two clamps whose tops sit at Z = 12 mm, and a declared minimum fixture
clearance of 3 mm. The part is an 80 × 60 × 20 mm block with a 12 mm deep rounded pocket and four
6 mm blind holes. The job starts from an explicitly labelled **naive shop recipe**: the short end
mill, and a 5 mm clearance plane.

```
state -> cad_building
state -> planning
state -> checking
  FAIL  tool_cutting_reach   actual=8.0 required=12.0 mm
        hint: Select an available tool with sufficient cutting reach; preserve the requested depth.
ATTEMPT 0 -> failed_checks
state -> repairing
  DIFF  ['op_pocket_1 tool EM6-S -> EM6-L']
state -> checking -> compiling -> path_checking -> simulating
ATTEMPT 1 -> failed_simulation
state -> repairing
  DIFF  ['clearance 5.0 -> 15.0 mm']
state -> checking -> compiling -> path_checking -> simulating
ATTEMPT 2 -> passed
JOB -> passed
```

**Attempt 0** never reaches simulation. The pocket is 12.0 mm deep and the selected tool can cut
8.0 mm, so `tool_cutting_reach` rejects it in microseconds. No machine time is spent on a plan
that was arithmetically impossible.

**Attempt 1** fixes the reach — the diff is exactly `EM6-S -> EM6-L` — and now passes preflight,
compiles to a 136-segment trajectory, and enters simulation. There it fails for a different
reason: the first lateral traverse runs at Z = 5 mm while the front clamp's top is at Z = 12 mm,
so the cutter strikes `clamp_front` on segment `s0005` at (35.589, −8.843, 5.0) mm, 0.157 mm in.
That is swept-volume geometry against a real fixture solid, not a rendering artefact.

**Attempt 2** raises the clearance plane from 5.0 to 15.0 mm — clearing the 12 mm clamp by
exactly the shop's declared 3 mm minimum — and passes: residual 0.0 mm, gouge 0.0 mm, all five
features at full coverage, simulated in ~0.2 s on a 0.5 mm grid.

Across all three attempts the confirmed design hash `d5cc67abc896ce03` is **unchanged**. The
agent fixed the process three times over and never touched the part.

---

## 7. Loop B — improvement across jobs

Loop A repairs one job. Loop B makes the *next* job cheaper by moving a discovery earlier.

The clamp collision in attempt 1 cost a full stock simulation to find. But the information needed
to reject that plan — the clearance plane height, the fixture solids, the tool envelope — was
available before the simulator ran. So the check was **promoted** out of the simulator into the
`path` stage as `path_fixture_envelope`, enabled under `policy-v1`.

Promotion is a governed process, not an edit:

1. Run the baseline policy over the frozen development fixtures and record the failures.
2. Propose one bounded change, from a **trusted template** with bounded parameters — never
   model-written code, imports or expressions.
3. Validate it independently of whatever proposed it: it must catch the original evidenced
   failure, catch at least one structurally different applicable failure, and **accept every
   known-valid boundary case**. Out-of-scope inputs must report *not applicable*, not failure.
4. Compare on the fixed development set, then evaluate once against untouched holdout.
5. Promote only if hard correctness is preserved.

Measured result, reproducible with `uv run python -m silta.evaluation --holdout`:

| Split | Policy | Expectations matched | False accepts | False rejects | Simulations run |
| --- | --- | --- | --- | --- | --- |
| development (8) | policy-v0 | 8/8 | 0 | 0 | 4 |
| development (8) | policy-v1 | 8/8 | 0 | 0 | **3** |
| holdout (4) | policy-v0 | 4/4 | 0 | 0 | 2 |
| holdout (4) | policy-v1 | 4/4 | 0 | 0 | 2 |

One simulation saved out of four, with zero false accepts and zero false rejects. Counts, with
denominators — 12 fixtures is a mechanism demonstration, not a reliability claim.

### The failure that validates the process

Version 1 of the promoted check was **wrong**. It compared the *holder's* radius against the
*tool tip's* height, so a perfectly safe vertical retract 9.85 mm away from a clamp was reported
as passing 23 mm below it. The stock simulator, which models each tool part at its own height,
said the same path was fine.

A frozen boundary fixture caught it — `holdout_03_valid_complex`, a valid case that version 1
falsely rejected. Version 2 tests each tool part (cutter, shank, holder) at its **own radius and
its own height above the tip**, reusing the simulator's own tool model so the two cannot
disagree. It blocks only a definite geometric overlap and merely *warns* when clearance is
thinner than the shop minimum, deferring to the simulator rather than rejecting a path that may
be fine.

This is why the corpus contains deliberately valid near-boundary cases: a check that rejects
good work is not a safer check, it is a broken one.

---

## 8. Loop C — memory across runs

The third loop stores what was learned so a later run does not rediscover it.

- **Episodes** — completed attempts with their evidence.
- **Recipes** — a plan that was verified end to end, recallable for an identical design, shop,
  policy and validator fingerprint.
- **Lessons** — bounded instructions derived from recurring diagnostic codes, with structured
  applicability predicates and explicit provenance. A lesson stays `proposed` until validated.

Two safeguards matter:

**Recall never bypasses verification.** A recalled recipe is re-checked and re-simulated under
the *current* checks. The namespace key includes the policy version and a validator fingerprint,
so a recipe verified under one policy is not silently replayed as if it had passed under another.

**Scope is narrow.** Only the exact synthetic demo fixture shares memory across browser sessions;
any uploaded drawing, any changed design or shop hash falls back to a per-session scope. A public
visitor may propose a lesson; promoting one into shared defaults is an operator action.

Memory is **off** for the automatic demo run. It has to be: once a passing recipe exists for the
public fixture, recall replays it on attempt 0 and every later visitor sees one candidate and no
loop — the failure-repair-pass story the product exists to show would never happen. Turn it on
from the operator controls to demonstrate recall deliberately.

---

## 9. Budgets, and why they are shared

Every model call — interpretation, planning, repair, schema repair, supervision — draws on one
budget:

| Bound | Default |
| --- | --- |
| Candidate plans | 3 |
| Total model calls | 6 |
| Job deadline | 120 s |
| Per-call timeout | 45 s |
| Output tokens per call | 4 000 |

There is no hidden nested retry loop. A schema-invalid response gets **one** repair attempt,
counted. Transient 429/5xx errors are retried at most twice with bounded backoff, always inside
the job deadline. Authentication failures stop immediately — they will not fix themselves. A
truncated response (`finish_reason` other than `stop`) is a failure, never a partial answer.

Switching provider is a separate recorded configuration, never a silent benchmark fallback. When
no inference key is configured the app uses a deterministic planner and **says so in its header**
— it never presents a deterministic plan as live inference.

---

## 10. What this is not

- **Not model training.** No weights are updated. This is runtime repair, policy improvement and
  recipe reuse. RL over this environment is plausible future work, not what runs today.
- **Not a full machine simulation.** It is geometric 2.5D stock removal and swept collision. It
  cannot validate undercuts, five-axis motion, deflection, cutting forces, chatter, thermal
  behaviour or machine dynamics.
- **Not a cycle-time measurement.** Estimated machining time is arithmetic from feeds and
  declared constants. Animation speed is not machining speed.
- **Not G-code.** No postprocessor, no controller dialect, no machine execution. The trajectory
  is a replay and verification format.
- **Not a certification.** These are prototype checks on a synthetic demonstration part, with a
  0.5 mm simulation grid. A 0.5 mm grid is not proof of 0.05 mm manufacturing accuracy.

---

## 11. Reproducing the evidence

```sh
make check                                  # ruff + the full offline test suite
uv run python -m silta.evaluation --holdout # policy comparison, development and holdout
make app                                    # the workbench; the demo job runs on load
make evals                                  # the experiment notebook
uv run python scripts/smoke_remote.py <URL> # remote acceptance against the deployed service
```

Related reading: [architecture](architecture.md) for the contracts and thresholds,
[plan](plan.md) for scope and metrics, [policies/](../policies/) for the promotion records, and
[docs/evidence/](evidence/) for the verification reports.
