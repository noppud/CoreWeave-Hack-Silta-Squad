"""Explicit scripted adapter for tests/rehearsal. Never an Astra fallback."""

from .common import save
from .demo import reference_moves


class Rehearsal:
    mode = "rehearsal"

    def __init__(self, evidence_dir):
        self.root = evidence_dir
        self.calls = 0

    def ask(self, role, context):
        self.calls += 1
        if role == "planner":
            job = context["fixed_job"]
            fast = bool(context["active_guidance"] or context["supervisor_instructions"])
            value = dict(
                summary="Scripted repair and feed improvement"
                if fast
                else "Scripted pocket-depth repair",
                moves=reference_moves(job, feed=240 if fast else 120),
            )
        elif role == "check_learner":
            value = dict(
                rule="feature_floor",
                reason="Reject cuts below a capsule pocket's accepted floor before simulation",
            )
        elif role == "supervisor":
            assert not ({"job", "candidate", "moves", "feature", "result", "history"} & context.keys())
            times = context["verified_time_history"]
            at_max = len(times) > 1
            value = dict(
                action="stop" if at_max else "improve",
                reason="Verified time improved; accept within this rehearsal budget.",
                guidance_proposal=(
                    "For capsule pockets, use the allowed feed limit and omit unnecessary dwell."
                )
                if context["guidance_evaluation_available"]
                else None,
            )
        else:
            raise ValueError(role)
        path = self.root / f"rehearsal-{self.calls:03d}.json"
        save(path, dict(mode=self.mode, role=role, value=value))
        return value, str(path)
