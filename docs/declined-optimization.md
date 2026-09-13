# A declined optimization preserves the verified plan

UMC11 exposed a controller edge case. After candidate0003 passed actual Fusion and stock conformity at4242.119344 estimated seconds, the supervisor proposed reducing ramp clearance. The planner could not establish the stated entry-stock prerequisite from the available evidence and declined before executing source. `runs/demo-umc-umc-11-recovery3/manifest.json` retains that incomplete historical job unchanged.

The controller now records `cam_proposal_unresolved` and returns the already verified incumbent, its original verdict and the decline explanation to the supervisor. The supervisor can choose another trial or stop. It does not receive the declined proposal as a verified candidate. Missing information before the first verified plan still leaves the job incomplete. Unknown simulation results still stop collection; they do not take this route.

This implements the existing pass-only supervisor and best-verified-plan contract. It adds no agent role or persistent learning file. Candidate/input/target/evidence integrity is checked again before review; attempt limits remain in force.

Validation:62 controller, agent and resume tests passed, including first-CAM decline without supervisor access and a declined second proposal returning the existing pass without another simulation. The fresh follow-up job is `runs/demo-umc-umc-11-recovery4/manifest.json`; consult its status for live completion.
