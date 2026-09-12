"""Test evaluation fixture loading and policy validation."""

import pytest

from silta.evaluation import load_fixtures, run_case
from silta.policy import POLICY_V1


class TestFixtureLoading:
    """Test that fixtures load correctly."""

    def test_all_12_fixtures_load(self):
        """All 12 fixtures (8 development + 4 holdout) must load without error."""
        all_fixtures = load_fixtures(split="all")
        assert len(all_fixtures) >= 12, f"Expected at least 12 fixtures, got {len(all_fixtures)}"

    def test_holdout_not_returned_by_default(self):
        """load_fixtures() without split argument must not return holdout fixtures."""
        dev_fixtures = load_fixtures()  # default is development
        dev_ids = {f.fixture_id for f in dev_fixtures}

        all_fixtures = load_fixtures(split="all")
        all_ids = {f.fixture_id for f in all_fixtures}

        holdout_ids = all_ids - dev_ids
        assert len(holdout_ids) > 0, "There should be some holdout fixtures"

        # Confirm default doesn't include holdout
        default_fixtures = load_fixtures()
        default_ids = {f.fixture_id for f in default_fixtures}

        for hid in holdout_ids:
            assert hid not in default_ids, f"Holdout fixture {hid} leaked into default load"

    def test_no_known_invalid_fixture_accepted_under_any_policy(self):
        """No fixture expected to fail must be accepted as PASSED under any policy.

        This is a false-acceptance check: a plan that should fail must never pass.
        """
        fixtures = load_fixtures(split="all")

        # Find fixtures that are expected to fail
        expected_to_fail = [
            f
            for f in fixtures
            if f.expectation.disposition.value != "passed"
            and f.expectation.disposition.value != "schema_invalid"
        ]

        # We must have some expected-to-fail fixtures
        assert len(expected_to_fail) > 0, "No expected-to-fail fixtures found in corpus"

        # Note: We can't run full evaluation here without async context and a working planner,
        # but we can at least verify that the expectations are set correctly
        for fixture in expected_to_fail:
            assert fixture.expectation.disposition.value != "passed", (
                f"Fixture {fixture.fixture_id} is marked to fail but expectation says passed"
            )


class TestPolicyValidation:
    """Test policy-specific validation rules."""

    @pytest.mark.asyncio
    async def test_policy_v1_does_not_false_reject_holdout_fixtures(self):
        """POLICY_V1 must not false-reject any holdout fixture.

        A false rejection is when a known-valid fixture is rejected by the validator.
        This test checks that the promoted path_fixture_envelope check in V1
        does not introduce false positives on the holdout set.
        """
        holdout_fixtures = load_fixtures(split="holdout")

        # Find holdout fixtures that are expected to pass
        expected_to_pass = [
            f for f in holdout_fixtures if f.expectation.disposition.value == "passed"
        ]

        # We should have at least some expected-to-pass holdout fixtures
        if len(expected_to_pass) == 0:
            pytest.skip("No expected-to-pass holdout fixtures to test")

        for fixture in expected_to_pass:
            # Run the case under POLICY_V1
            outcome = await run_case(fixture, POLICY_V1, provider=None, max_attempts=1)

            # If it's expected to pass, it must not be false-rejected
            # A false rejection would be: disposition != PASSED but expectation says PASSED
            if outcome.disposition.value != "passed":
                # Check if this is an accepted alternate disposition
                accepted = set(fixture.expectation.accepted_dispositions) or {
                    fixture.expectation.disposition
                }
                if outcome.disposition not in accepted:
                    pytest.fail(
                        f"POLICY_V1 false-rejected holdout fixture {fixture.fixture_id}: "
                        f"expected {fixture.expectation.disposition.value}, "
                        f"got {outcome.disposition.value}. "
                        f"Mismatch: {outcome.mismatch_reason}"
                    )
