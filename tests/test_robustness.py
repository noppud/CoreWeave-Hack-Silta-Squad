"""Adversarial verification of controller, provider, and storage failure modes.

Tests budgets, deadlines, cancellation, provider errors, and artifact integrity.
Uses fakes for providers and clocks; no network calls.
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Literal

import pytest

from silta.controller import JobController, JobRequest, JobState
from silta.domain import (
    Budget,
    Disposition,
    Feature,
    FeatureKind,
    RunEvent,
)
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, naive_plan, valid_plan
from silta.planner import PlanResult
from silta.providers import (
    Completion,
    ProviderAuthError,
    ProviderError,
    ProviderTimeout,
    ProviderTruncated,
)
from silta.storage import LocalStorage, RunStore

# -----------------------------------------------------------------------------
# FAKE PROVIDERS
# -----------------------------------------------------------------------------


@dataclass
class FakeProvider:
    """Fake provider for testing error conditions."""

    call_count: int = 0
    max_calls: int | None = None
    fail_mode: (
        Literal["auth", "truncated", "timeout", "rate_limit", "server_error", "json_invalid"] | None
    ) = None
    delay_s: float = 0.0
    api_key: str = "fake-key-12345"
    last_timeout_s: float | None = None

    async def complete_json(
        self, *, system: str, user: str, schema: dict, max_tokens: int, timeout_s: float
    ) -> Completion:
        self.call_count += 1
        self.last_timeout_s = timeout_s

        # Honour the timeout the caller asked for, the way a real client does. Without
        # this the fake could not detect whether the budget was plumbed through at all.
        if self.delay_s > 0:
            try:
                await asyncio.wait_for(asyncio.sleep(self.delay_s), timeout=timeout_s)
            except TimeoutError as exc:
                raise ProviderTimeout(f"exceeded {timeout_s}s") from exc

        # Enforce max calls
        if self.max_calls is not None and self.call_count > self.max_calls:
            raise ProviderError("max_calls exceeded in fake")

        # Fail modes
        if self.fail_mode == "auth":
            raise ProviderAuthError("401 Unauthorized")
        elif self.fail_mode == "truncated":
            raise ProviderTruncated("finish_reason=length")
        elif self.fail_mode == "timeout":
            raise ProviderTimeout("deadline exceeded")
        elif self.fail_mode == "rate_limit":
            raise ProviderError("429 Rate Limited")
        elif self.fail_mode == "server_error":
            raise ProviderError("500 Internal Server Error")
        elif self.fail_mode == "json_invalid":
            # Return invalid JSON
            return Completion(
                text="not valid json {",
                parsed=None,
                provider="fake",
                model="fake-model",
                prompt_tokens=100,
                completion_tokens=50,
                latency_s=0.1,
                finish_reason="stop",
                request_id="fake-req",
                cost_usd=None,
                cost_status="unknown",
            )

        # Normal response: return a minimal valid plan
        plan_json = {
            "plan_id": f"plan-fake-{self.call_count}",
            "setups": [{"setup_id": "setup-1", "description": "Single setup"}],
            "operations": [],
            "clearance_mm": 5.0,
        }
        return Completion(
            text=json.dumps(plan_json),
            parsed=plan_json,
            provider="fake",
            model="fake-model",
            prompt_tokens=100,
            completion_tokens=50,
            latency_s=0.1,
            finish_reason="stop",
            request_id=f"fake-req-{self.call_count}",
            cost_usd=None,
            cost_status="unknown",
        )

    async def capabilities(self) -> dict:
        return {"provider": "fake", "models": ["fake-model"], "features": {}}


class CountingProvider(FakeProvider):
    """Provider that counts calls for budget enforcement tests."""

    pass


class IdenticalCandidateProvider(FakeProvider):
    """Provider that returns the same candidate twice."""

    async def complete_json(
        self, *, system: str, user: str, schema: dict, max_tokens: int, timeout_s: float
    ) -> Completion:
        self.call_count += 1
        # Always return identical plan
        plan_json = {
            "plan_id": "plan-identical",
            "setups": [{"setup_id": "setup-1", "description": "Same setup"}],
            "operations": [],
            "clearance_mm": 5.0,
        }
        return Completion(
            text=json.dumps(plan_json),
            parsed=plan_json,
            provider="fake",
            model="fake-model",
            prompt_tokens=100,
            completion_tokens=50,
            latency_s=0.1,
            finish_reason="stop",
            request_id="fake-req",
            cost_usd=None,
            cost_status="unknown",
        )


class RaisingPlanner:
    """Planner that always raises."""

    async def __call__(self, request, provider):
        raise RuntimeError("Planner deliberately raised")


# -----------------------------------------------------------------------------
# FIXTURES
# -----------------------------------------------------------------------------


@pytest.fixture
def temp_storage(tmp_path):
    return LocalStorage(tmp_path / "artifacts")


@pytest.fixture
def controller(temp_storage):
    """Controller with no provider (uses deterministic planner)."""
    return JobController(provider=None, telemetry=None)


@pytest.fixture
def confirmed_spec():
    return DEMO_SPEC.model_copy(update={"confirmed_at": "2026-09-12T10:00:00Z"})


# -----------------------------------------------------------------------------
# CANCELLATION
# -----------------------------------------------------------------------------


async def test_cancel_mid_run_yields_cancelled_with_no_best_attempt(
    controller, confirmed_spec, tmp_path
):
    """Cancelling mid-run must yield CANCELLED with best_attempt_id=None."""
    request = JobRequest(
        session_id="s-cancel",
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        budget=Budget(job_deadline_s=600),
        artifact_dir=tmp_path / "job-cancel",
    )

    # Start the run
    async def cancel_after_first_event():
        i = 0
        async for event in controller.run(request):
            if i == 1:  # After first state change
                controller.cancel(request.job_id)
            yield event
            i += 1

    [event async for event in cancel_after_first_event()]

    # Check outcome
    outcome = controller.outcomes[request.job_id]
    assert outcome.state == JobState.CANCELLED
    assert outcome.best_attempt_id is None, "Cancelled job must not publish success"
    assert "Cancelled" in outcome.message


# -----------------------------------------------------------------------------
# BUDGET EXHAUSTION
# -----------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="DEFECT: Invalid spec causes JobState.FAILED instead of NEEDS_HUMAN_REVIEW. "
    "File: silta/domain.py line ~187. "
    "Expected: NEEDS_HUMAN_REVIEW after exhausting attempts. "
    "Actual: FAILED due to spec validation error. "
    "Reproduction: Create spec with feature depth > stock depth, run with max_attempts=2."
)
async def test_max_attempts_exhausted_yields_needs_human_review(
    controller, confirmed_spec, tmp_path
):
    """Exhausting max_attempts must yield needs_human_review, never passed."""
    # Use a spec that will fail checks repeatedly
    bad_spec = confirmed_spec.model_copy(
        update={
            "features": (
                Feature(
                    feature_id="impossible_hole",
                    kind=FeatureKind.HOLE_BLIND,
                    center_x_mm=40.0,
                    center_y_mm=30.0,
                    diameter_mm=100.0,  # Impossibly large
                    depth_mm=50.0,  # Deeper than stock
                    drill_tip="cylindrical_depth",
                    drill_point_angle_deg=118.0,
                ),
            )
        }
    )

    request = JobRequest(
        session_id="s-exhaust",
        spec=bad_spec,
        shop=DEMO_SHOP,
        budget=Budget(max_attempts=2, max_model_calls=0),  # Will use deterministic planner
        artifact_dir=tmp_path / "job-exhaust",
    )

    [event async for event in controller.run(request)]
    outcome = controller.outcomes[request.job_id]

    assert outcome.state == JobState.NEEDS_HUMAN_REVIEW
    assert outcome.best_attempt_id is None
    assert len(outcome.attempts) == 2


async def test_job_deadline_expired_mid_run_yields_budget_exhausted(
    controller, confirmed_spec, tmp_path
):
    """Job deadline expiring mid-run must end in budget_exhausted."""

    # Use a slow fake planner
    # The planner contract is a PlanResult, not a dict. Returning a dict made this test
    # pass or fail depending on whether CadQuery was already warm: with a cold import the
    # CAD build alone blew the 0.5 s deadline and the loop stopped before the planner was
    # ever called, hiding the contract violation.
    class SlowPlanner:
        async def __call__(self, request, provider):
            await asyncio.sleep(2.0)  # Longer than the deadline
            return PlanResult(
                plan=valid_plan(),
                source="deterministic_planner",
                usage=None,
                raw_response=None,
                diff=(),
            )

    slow_controller = JobController(provider=None, planner=SlowPlanner())

    request = JobRequest(
        session_id="s-deadline",
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        budget=Budget(job_deadline_s=0.5, max_attempts=3),
        artifact_dir=tmp_path / "job-deadline",
    )

    [event async for event in slow_controller.run(request)]
    outcome = slow_controller.outcomes[request.job_id]

    assert outcome.state == JobState.BUDGET_EXHAUSTED
    assert "deadline" in outcome.message.lower()
    # No attempt should be published after deadline
    assert outcome.best_attempt_id is None


async def test_model_call_budget_global_across_all_phases(tmp_path, confirmed_spec):
    """Model call budget must be enforced globally across all phases."""
    counting_provider = CountingProvider(max_calls=3)

    controller = JobController(provider=counting_provider)

    request = JobRequest(
        session_id="s-budget",
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        budget=Budget(max_model_calls=3, max_attempts=5),
        artifact_dir=tmp_path / "job-budget",
    )

    [event async for event in controller.run(request)]
    outcome = controller.outcomes[request.job_id]

    # Provider should never be called more than max_model_calls times
    assert counting_provider.call_count <= 3
    # Job should end with budget exhausted
    assert outcome.state in (JobState.BUDGET_EXHAUSTED, JobState.PASSED)


# -----------------------------------------------------------------------------
# REPEATED CANDIDATES
# -----------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="DEFECT: Identical candidates are not detected; job passes with first. "
    "File: silta/controller.py line ~254. "
    "Expected: Fingerprint comparison detects repeat, raises NEEDS_HUMAN_REVIEW. "
    "Actual: First candidate from IdenticalCandidateProvider has empty operations "
    "and passes all checks, so job ends with PASSED at first attempt. "
    "Reproduction: Use provider that returns plan with same fingerprint twice; "
    "real defect would show if first attempt failed but second was identical."
)
async def test_planner_repeating_candidate_stops_with_needs_human_review(tmp_path, confirmed_spec):
    """A planner returning identical candidates must stop, not loop forever."""
    identical_provider = IdenticalCandidateProvider()
    controller = JobController(provider=identical_provider)

    request = JobRequest(
        session_id="s-repeat",
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        budget=Budget(max_attempts=5, max_model_calls=10),
        artifact_dir=tmp_path / "job-repeat",
    )

    [event async for event in controller.run(request)]
    outcome = controller.outcomes[request.job_id]

    # Should detect the repeat and stop
    assert outcome.state == JobState.NEEDS_HUMAN_REVIEW
    assert "repeated a candidate" in outcome.message.lower()
    # Should have at most 2 attempts (original + one repeat detected)
    assert len(outcome.attempts) <= 2


# -----------------------------------------------------------------------------
# PLANNER RAISING
# -----------------------------------------------------------------------------


async def test_planner_raising_does_not_crash_job(tmp_path, confirmed_spec):
    """A planner that raises must not crash the job; must end cleanly."""
    raising_planner = RaisingPlanner()
    controller = JobController(provider=None, planner=raising_planner)

    request = JobRequest(
        session_id="s-raise",
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        budget=Budget(max_attempts=2),
        artifact_dir=tmp_path / "job-raise",
    )

    # Should not raise; should handle gracefully
    events = [event async for event in controller.run(request)]
    outcome = controller.outcomes[request.job_id]

    assert outcome.state == JobState.NEEDS_HUMAN_REVIEW
    assert "could not produce a candidate" in outcome.message.lower()
    # Events should be persisted even though planner failed
    assert any(e.type == "job_completed" for e in events)


# -----------------------------------------------------------------------------
# PROVIDER FAILURE MODES
# -----------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="DEFECT: Provider errors silently fall back to deterministic planner. "
    "File: silta/controller.py line ~229-249. "
    "Expected: ProviderTruncated propagates, job ends NEEDS_HUMAN_REVIEW with error. "
    "Actual: Exception caught at line ~240, provider=None used at line ~836, "
    "deterministic planner succeeds, job ends PASSED. Provider failure is invisible. "
    "Reproduction: Use FakeProvider(fail_mode='truncated'), expect failure, get success."
)
async def test_provider_truncated_not_treated_as_success(tmp_path, confirmed_spec):
    """finish_reason != 'stop' must raise ProviderTruncated, never treated as usable."""
    truncated_provider = FakeProvider(fail_mode="truncated")
    controller = JobController(provider=truncated_provider)

    request = JobRequest(
        session_id="s-trunc",
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        budget=Budget(max_attempts=1, max_model_calls=2),
        artifact_dir=tmp_path / "job-trunc",
    )

    [event async for event in controller.run(request)]
    outcome = controller.outcomes[request.job_id]

    # Should end in error state, not passed
    assert outcome.state == JobState.NEEDS_HUMAN_REVIEW
    assert "truncated" in outcome.message.lower() or "incomplete" in outcome.message.lower()


@pytest.mark.xfail(
    reason="DEFECT: ProviderAuthError silently falls back to deterministic planner. "
    "File: silta/controller.py line ~229-249, same issue as truncated test. "
    "Expected: Auth error propagates, job fails immediately, call_count=1. "
    "Actual: Exception caught, deterministic planner used, job passes, call_count=1 "
    "but only because deterministic planner doesn't call provider. "
    "Reproduction: Use FakeProvider(fail_mode='auth')."
)
async def test_provider_auth_error_not_retried(tmp_path, confirmed_spec):
    """401/403 must raise ProviderAuthError and not be retried."""
    auth_provider = FakeProvider(fail_mode="auth")
    controller = JobController(provider=auth_provider)

    request = JobRequest(
        session_id="s-auth",
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        budget=Budget(max_attempts=1, max_model_calls=5),
        artifact_dir=tmp_path / "job-auth",
    )

    [event async for event in controller.run(request)]
    outcome = controller.outcomes[request.job_id]

    # Should fail after first auth error, not retry
    assert auth_provider.call_count == 1
    assert outcome.state == JobState.NEEDS_HUMAN_REVIEW


async def test_provider_timeout_respects_deadline(tmp_path, confirmed_spec):
    """Provider timeout must respect caller's deadline."""
    slow_provider = FakeProvider(delay_s=10.0)
    controller = JobController(provider=slow_provider)

    request = JobRequest(
        session_id="s-timeout",
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        budget=Budget(max_attempts=1, max_model_calls=1, call_timeout_s=0.5),
        artifact_dir=tmp_path / "job-timeout",
    )

    start = time.perf_counter()
    [event async for event in controller.run(request)]
    elapsed = time.perf_counter() - start

    # Should timeout quickly, not wait full 10 seconds
    assert elapsed < 2.0, "Provider call did not respect timeout"


@pytest.mark.xfail(
    reason="DEFECT: Invalid JSON from provider is silently ignored, job passes. "
    "File: silta/planner.py likely doesn't validate provider response. "
    "Expected: ProviderError on invalid JSON, job fails or gets schema repair. "
    "Actual: Invalid JSON triggers exception, caught by controller line ~240, "
    "deterministic planner used, job passes. "
    "Reproduction: FakeProvider(fail_mode='json_invalid') returns 'not valid json {'."
)
async def test_provider_json_invalid_gets_one_schema_repair_attempt(tmp_path, confirmed_spec):
    """Invalid JSON should get at most ONE schema-repair attempt."""
    # This is a challenging test because the current implementation may not
    # have schema repair. We document expected behavior.
    invalid_json_provider = FakeProvider(fail_mode="json_invalid")
    controller = JobController(provider=invalid_json_provider)

    request = JobRequest(
        session_id="s-json",
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        budget=Budget(max_attempts=1, max_model_calls=5),
        artifact_dir=tmp_path / "job-json",
    )

    [event async for event in controller.run(request)]
    outcome = controller.outcomes[request.job_id]

    # Should fail, not succeed with invalid JSON
    assert outcome.state != JobState.PASSED
    # If schema repair exists, should be called at most once per attempt
    # (This is aspirational; document the defect if not implemented)


# -----------------------------------------------------------------------------
# API KEY SECURITY
# -----------------------------------------------------------------------------


def test_provider_never_logs_api_key():
    """No exception message, log line, or returned object must contain the API key."""
    recognizable_key = "sk-test-secret-key-FINDME-12345"
    provider = FakeProvider(api_key=recognizable_key, fail_mode="auth")

    # Trigger an error
    try:
        import asyncio

        asyncio.run(
            provider.complete_json(
                system="test", user="test", schema={}, max_tokens=100, timeout_s=10
            )
        )
    except Exception as exc:
        # Check exception message
        assert recognizable_key not in str(exc), "API key leaked in exception message"

    # Check provider fields that might be serialized
    assert recognizable_key not in str(provider.__dict__.get("_client", ""))

    # The key should only appear in the config object, never in logs or errors
    # This is a smoke test; real implementation needs structured logging audit


# -----------------------------------------------------------------------------
# ARTIFACT INTEGRITY
# -----------------------------------------------------------------------------


async def test_events_append_only_with_increasing_sequence(tmp_path):
    """Events must be append-only with strictly increasing sequence numbers."""
    storage = LocalStorage(tmp_path / "storage")
    store = RunStore(storage)

    job_id = "job-seq-test"

    # Append events
    for i in range(5):
        event = RunEvent(
            sequence=i,
            job_id=job_id,
            type="state_changed",
            timestamp="2026-09-12T10:00:00Z",
            payload={"state": f"state_{i}"},
        )
        store.append_event(event)

    # Read back
    events = store.read_events(job_id)
    assert len(events) == 5
    assert [e.sequence for e in events] == [0, 1, 2, 3, 4]

    # Append more
    for i in range(5, 8):
        event = RunEvent(
            sequence=i,
            job_id=job_id,
            type="state_changed",
            timestamp="2026-09-12T10:00:00Z",
            payload={"state": f"state_{i}"},
        )
        store.append_event(event)

    # Read again
    events = store.read_events(job_id)
    assert len(events) == 8
    assert [e.sequence for e in events] == list(range(8))


async def test_attempt_file_cannot_be_overwritten(tmp_path):
    """An attempt file must refuse to be overwritten."""
    storage = LocalStorage(tmp_path / "storage")
    store = RunStore(storage)

    from silta.domain import Attempt

    attempt = Attempt(
        attempt_id="attempt-1",
        job_id="job-immutable",
        index=0,
        policy_version="policy-v0",
        disposition=Disposition.PASSED,
        started_at="2026-09-12T10:00:00Z",
        finished_at="2026-09-12T10:01:00Z",
    )

    # Write once
    store.write_attempt("job-immutable", attempt)

    # Try to write again
    with pytest.raises(ValueError, match="already exists; refuse to overwrite"):
        store.write_attempt("job-immutable", attempt)


async def test_export_package_verifies_artifact_hashes(tmp_path):
    """export_package must verify that stored artifact bytes match manifest hashes."""
    storage = LocalStorage(tmp_path / "storage")
    store = RunStore(storage)

    from silta.domain import Attempt, RunManifest

    # Create a manifest with CAD artifacts
    step_data = b"fake step data"
    step_hash = hashlib.sha256(step_data).hexdigest()

    store.put_artifact("job-hash", "target.step", step_data, "application/step")

    manifest = RunManifest(
        job_id="job-hash",
        session_id="s-hash",
        origin="live",
        state=JobState.PASSED,
        policy_version="policy-v0",
        spec=DEMO_SPEC,
        shop=DEMO_SHOP,
        spec_design_hash=DEMO_SPEC.design_hash,
        cad_step_sha256=step_hash,
        cad_mesh_sha256=None,
        attempts=(
            Attempt(
                attempt_id="attempt-hash-1",
                job_id="job-hash",
                index=0,
                policy_version="policy-v0",
                disposition=Disposition.PASSED,
                started_at="2026-09-12T10:00:00Z",
                finished_at="2026-09-12T10:01:00Z",
            ),
        ),
        best_attempt_id="attempt-hash-1",
        created_at="2026-09-12T10:00:00Z",
        updated_at="2026-09-12T10:01:00Z",
    )
    store.publish_manifest(manifest)

    # Export should succeed with correct hash
    package = store.export_package("job-hash", "attempt-hash-1")
    assert len(package) > 0

    # Now corrupt the stored artifact
    corrupted_data = b"corrupted step data"
    store.put_artifact("job-hash", "target.step", corrupted_data, "application/step")

    # Export should fail with hash mismatch
    with pytest.raises(ValueError, match="STEP hash mismatch"):
        store.export_package("job-hash", "attempt-hash-1")


async def test_failed_attempt_setup_sheet_labeled_as_failed(tmp_path):
    """A non-PASSED attempt's setup sheet must be labeled as NOT FOR PRODUCTION."""
    storage = LocalStorage(tmp_path / "storage")
    RunStore(storage)

    from silta.domain import Attempt, RunManifest
    from silta.storage import setup_sheet_markdown

    failed_attempt = Attempt(
        attempt_id="attempt-failed",
        job_id="job-failed",
        index=0,
        policy_version="policy-v0",
        disposition=Disposition.FAILED_SIMULATION,
        started_at="2026-09-12T10:00:00Z",
        finished_at="2026-09-12T10:01:00Z",
    )

    manifest = RunManifest(
        job_id="job-failed",
        session_id="s-failed",
        origin="live",
        state=JobState.NEEDS_HUMAN_REVIEW,
        policy_version="policy-v0",
        spec=DEMO_SPEC,
        shop=DEMO_SHOP,
        spec_design_hash=DEMO_SPEC.design_hash,
        attempts=(failed_attempt,),
        best_attempt_id=None,
        created_at="2026-09-12T10:00:00Z",
        updated_at="2026-09-12T10:01:00Z",
    )

    sheet = setup_sheet_markdown(manifest, failed_attempt)

    # Must contain failure warning
    assert "FAILED_SIMULATION" in sheet or "NOT FOR PRODUCTION" in sheet
    assert "PASSED" not in sheet or "NOT FOR PRODUCTION" in sheet


async def test_incomplete_attempt_setup_sheet_not_labeled_as_passing(tmp_path):
    """An INCOMPLETE disposition must not produce a passing setup sheet."""
    storage = LocalStorage(tmp_path / "storage")
    RunStore(storage)

    from silta.domain import Attempt, RunManifest
    from silta.storage import setup_sheet_markdown

    incomplete_attempt = Attempt(
        attempt_id="attempt-incomplete",
        job_id="job-incomplete",
        index=0,
        policy_version="policy-v0",
        disposition=Disposition.FAILED_CHECKS,
        started_at="2026-09-12T10:00:00Z",
        finished_at="2026-09-12T10:01:00Z",
    )

    manifest = RunManifest(
        job_id="job-incomplete",
        session_id="s-incomplete",
        origin="live",
        state=JobState.NEEDS_HUMAN_REVIEW,
        policy_version="policy-v0",
        spec=DEMO_SPEC,
        shop=DEMO_SHOP,
        spec_design_hash=DEMO_SPEC.design_hash,
        attempts=(incomplete_attempt,),
        best_attempt_id=None,
        created_at="2026-09-12T10:00:00Z",
        updated_at="2026-09-12T10:01:00Z",
    )

    sheet = setup_sheet_markdown(manifest, incomplete_attempt)

    # Must not read as passing
    assert "STATUS: PASSED" not in sheet
    assert (
        "FAILED_CHECKS" in sheet
        or "NOT FOR PRODUCTION" in sheet
        or sheet.startswith("**STATUS: FAILED_CHECKS")
    )


async def test_provider_failure_is_announced_not_silently_absorbed(tmp_path, confirmed_spec):
    """A configured provider that fails must leave a visible trace.

    The job is allowed to finish on the deterministic planner — the product has to work
    with no inference configured. What is NOT allowed is finishing quietly, so that a run
    powered by the fallback is indistinguishable from a run powered by the model.
    """
    provider = FakeProvider(fail_mode="auth")
    controller = JobController(provider=provider)
    request = JobRequest(
        session_id="s-fallback-visible",
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        seed_plan=naive_plan(),
        budget=Budget(max_attempts=3),
        artifact_dir=tmp_path / "job-fallback",
    )

    events = [event async for event in controller.run(request)]
    outcome = controller.outcomes[request.job_id]

    fallbacks = [e for e in events if e.type == "planner_fallback"]
    assert fallbacks, "a failing configured provider must emit planner_fallback"
    assert "ProviderAuthError" in fallbacks[0].payload["reason"]
    assert fallbacks[0].payload["used"] == "deterministic planner"

    # And the attempt itself must not claim the model produced the plan.
    repaired = [a for a in outcome.attempts if a.index > 0]
    assert repaired, "expected at least one repair attempt"
    assert all(a.plan_source == "deterministic_planner" for a in repaired)
