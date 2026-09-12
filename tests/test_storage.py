"""Test storage, persistence and export package integrity."""

import tempfile
from pathlib import Path

import pytest

from silta.domain import Attempt, Disposition, RunEvent, RunManifest, utc_now
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, valid_plan
from silta.storage import LocalStorage, RunStore


class TestLocalStorage:
    """Test the local filesystem storage backend."""

    def test_put_and_get_roundtrip(self):
        """Bytes written must be readable back exactly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(Path(tmpdir))
            data = b"test content"

            storage.put_bytes("test/file.txt", data, "text/plain")

            retrieved = storage.get_bytes("test/file.txt")
            assert retrieved == data

    def test_exists_check(self):
        """exists() must return True for written keys and False otherwise."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(Path(tmpdir))

            assert not storage.exists("missing.txt")

            storage.put_bytes("exists.txt", b"data", "text/plain")
            assert storage.exists("exists.txt")

    def test_invalid_keys_rejected(self):
        """Keys with .., absolute paths or backslashes must be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(Path(tmpdir))

            with pytest.raises(ValueError, match="Invalid storage key"):
                storage.put_bytes("../escape", b"data", "text/plain")

            with pytest.raises(ValueError, match="Invalid storage key"):
                storage.put_bytes("/absolute", b"data", "text/plain")

            with pytest.raises(ValueError, match="Invalid storage key"):
                storage.put_bytes("back\\slash", b"data", "text/plain")


class TestRunStore:
    """Test high-level run persistence."""

    def test_events_are_append_only_with_increasing_sequence(self):
        """Events must be appended with increasing sequence numbers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(Path(tmpdir))
            store = RunStore(storage)

            event1 = RunEvent(
                sequence=0,
                job_id="job1",
                type="state_changed",
                timestamp=utc_now(),
                payload={"state": "planning"},
            )

            event2 = RunEvent(
                sequence=1,
                job_id="job1",
                type="state_changed",
                timestamp=utc_now(),
                payload={"state": "checking"},
            )

            store.append_event(event1)
            store.append_event(event2)

            events = store.read_events("job1")
            assert len(events) == 2
            assert events[0].sequence == 0
            assert events[1].sequence == 1

    def test_attempt_file_cannot_be_overwritten(self):
        """Writing an attempt with an existing attempt_id must raise."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(Path(tmpdir))
            store = RunStore(storage)

            attempt = Attempt(
                attempt_id="job1-a0",
                job_id="job1",
                index=0,
                policy_version="test",
                origin="live",
                disposition=Disposition.PASSED,
                started_at=utc_now(),
                finished_at=utc_now(),
            )

            store.write_attempt("job1", attempt)

            # Try to overwrite
            with pytest.raises(ValueError, match="already exists"):
                store.write_attempt("job1", attempt)

    def test_export_package_raises_on_tampered_artifact_hash(self):
        """export_package must raise if an artifact hash doesn't match the manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(Path(tmpdir))
            store = RunStore(storage)

            # Write a STEP file
            step_data = b"STEP file content"
            storage.put_bytes("artifacts/job1/target.step", step_data, "application/step")

            # Create a manifest with a wrong hash
            import hashlib

            wrong_hash = hashlib.sha256(b"different content").hexdigest()

            manifest = RunManifest(
                job_id="job1",
                session_id="session1",
                origin="live",
                state="passed",
                policy_version="test",
                spec=DEMO_SPEC,
                shop=DEMO_SHOP,
                spec_design_hash=DEMO_SPEC.design_hash,
                cad_step_sha256=wrong_hash,  # tampered
                created_at=utc_now(),
                updated_at=utc_now(),
                attempts=(
                    Attempt(
                        attempt_id="job1-a0",
                        job_id="job1",
                        index=0,
                        policy_version="test",
                        origin="live",
                        disposition=Disposition.PASSED,
                        plan=valid_plan(),
                        started_at=utc_now(),
                        finished_at=utc_now(),
                    ),
                ),
                best_attempt_id="job1-a0",
            )

            store.publish_manifest(manifest)

            # Export should raise due to hash mismatch
            with pytest.raises(ValueError, match="STEP hash mismatch"):
                store.export_package("job1", "job1-a0")

    def test_non_passed_attempt_cannot_yield_passing_setup_sheet(self):
        """A setup sheet for a non-PASSED attempt must contain a warning status."""
        from silta.storage import setup_sheet_markdown

        manifest = RunManifest(
            job_id="job1",
            session_id="session1",
            origin="live",
            state="needs_human_review",
            policy_version="test",
            spec=DEMO_SPEC,
            shop=DEMO_SHOP,
            spec_design_hash=DEMO_SPEC.design_hash,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

        failed_attempt = Attempt(
            attempt_id="job1-a0",
            job_id="job1",
            index=0,
            policy_version="test",
            origin="live",
            disposition=Disposition.FAILED_CHECKS,
            plan=valid_plan(),
            started_at=utc_now(),
            finished_at=utc_now(),
        )

        sheet = setup_sheet_markdown(manifest, failed_attempt)

        # The sheet must contain a warning
        assert "NOT FOR PRODUCTION" in sheet.upper(), "Failed attempt sheet must warn"
        assert "FAILED_CHECKS" in sheet.upper()

    def test_session_isolation_cannot_read_another_sessions_job(self):
        """list_jobs(session_id) must not return jobs from other sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(Path(tmpdir))
            store = RunStore(storage)

            # Create manifests for two sessions
            manifest1 = RunManifest(
                job_id="job1",
                session_id="session1",
                origin="live",
                state="passed",
                policy_version="test",
                spec=DEMO_SPEC,
                shop=DEMO_SHOP,
                spec_design_hash=DEMO_SPEC.design_hash,
                created_at=utc_now(),
                updated_at=utc_now(),
            )

            manifest2 = RunManifest(
                job_id="job2",
                session_id="session2",
                origin="live",
                state="passed",
                policy_version="test",
                spec=DEMO_SPEC,
                shop=DEMO_SHOP,
                spec_design_hash=DEMO_SPEC.design_hash,
                created_at=utc_now(),
                updated_at=utc_now(),
            )

            store.publish_manifest(manifest1)
            store.publish_manifest(manifest2)

            # List jobs for session1
            session1_jobs = store.list_jobs(session_id="session1")
            assert "job1" in session1_jobs
            assert "job2" not in session1_jobs

            # List jobs for session2
            session2_jobs = store.list_jobs(session_id="session2")
            assert "job2" in session2_jobs
            assert "job1" not in session2_jobs
