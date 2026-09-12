"""Adversarial verification of service session and request integrity.

Tests that would FAIL if the behaviour were wrong. No fixes applied; real defects
are documented as failing or xfail tests with precise reproductions.
"""

import hashlib

import pytest

from silta.domain import Budget, Units
from silta.fixtures import DEMO_SHOP, DEMO_SPEC
from silta.service import (
    MAX_UPLOAD_BYTES,
    AccessDenied,
    ConflictError,
    RunRequest,
    SiltaService,
)
from silta.storage import LocalStorage, RunStore


@pytest.fixture
def temp_storage(tmp_path):
    """Isolated storage for each test."""
    return LocalStorage(tmp_path / "artifacts")


@pytest.fixture
def service(temp_storage):
    """Service with local storage and no provider."""
    store = RunStore(temp_storage)
    return SiltaService(store=store, provider=None, artifact_root=temp_storage.root)


@pytest.fixture
def confirmed_spec():
    """A confirmed spec ready for runs."""
    return DEMO_SPEC.model_copy(update={"confirmed_at": "2026-09-12T10:00:00Z"})


# -----------------------------------------------------------------------------
# SESSION ISOLATION
# -----------------------------------------------------------------------------


async def test_load_run_from_wrong_session_raises_access_denied(service, confirmed_spec):
    """Two sessions cannot see each other's jobs: load_run must check ownership."""
    s1 = service.new_session_id()
    s2 = service.new_session_id()

    # Session 1 runs a job
    request = RunRequest(session_id=s1, spec=confirmed_spec, shop=DEMO_SHOP)
    events = [event async for event in service.run_job(request)]
    job_id = events[0].job_id

    # Session 2 tries to load it
    with pytest.raises(AccessDenied, match="belongs to another session"):
        service.load_run(s2, job_id)


async def test_outcome_from_wrong_session_raises_access_denied(service, confirmed_spec):
    """outcome() must also check ownership."""
    s1 = service.new_session_id()
    s2 = service.new_session_id()

    request = RunRequest(session_id=s1, spec=confirmed_spec, shop=DEMO_SHOP)
    events = [event async for event in service.run_job(request)]
    job_id = events[0].job_id

    with pytest.raises(AccessDenied, match="belongs to another session"):
        service.outcome(s2, job_id)


async def test_export_package_from_wrong_session_raises_access_denied(service, confirmed_spec):
    """export_package must check ownership."""
    s1 = service.new_session_id()
    s2 = service.new_session_id()

    request = RunRequest(session_id=s1, spec=confirmed_spec, shop=DEMO_SHOP)
    events = [event async for event in service.run_job(request)]
    job_id = events[0].job_id
    manifest = service.load_run(s1, job_id)
    attempt_id = manifest.attempts[0].attempt_id

    with pytest.raises(AccessDenied, match="belongs to another session"):
        service.export_package(s2, job_id, attempt_id)


async def test_cancel_job_from_wrong_session_raises_access_denied(service, confirmed_spec):
    """cancel_job must check ownership."""
    s1 = service.new_session_id()
    s2 = service.new_session_id()

    request = RunRequest(
        session_id=s1,
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        budget=Budget(job_deadline_s=600),  # long enough not to complete instantly
    )
    # Start the job asynchronously (don't await full completion)
    async_iter = service.run_job(request).__aiter__()
    first_event = await async_iter.__anext__()
    job_id = first_event.job_id

    # Session 2 tries to cancel it
    with pytest.raises(AccessDenied, match="belongs to another session"):
        service.cancel_job(s2, job_id)


# -----------------------------------------------------------------------------
# CONFIRM SPEC VALIDATION
# -----------------------------------------------------------------------------


def test_confirm_spec_with_stale_revision_raises_conflict(service):
    """Stale expected_revision must raise ConflictError."""
    session_id = service.new_session_id()

    service.session(session_id).proposals["fake-proposal"] = DEMO_SPEC.model_copy(
        update={
            "revision": 2,
            "proposal_id": "fake-proposal",
            "confirmed_at": None,
        }
    )

    with pytest.raises(ConflictError, match="moved to revision 2; you confirmed revision 1"):
        service.confirm_spec(
            session_id=session_id,
            proposal_id="fake-proposal",
            edits=None,
            expected_revision=1,
        )


def test_confirm_spec_with_unknown_units_raises(service):
    """Units.UNKNOWN cannot be confirmed."""
    session_id = service.new_session_id()

    proposal = DEMO_SPEC.model_copy(
        update={
            "units": Units.UNKNOWN,
            "proposal_id": "proposal-unknown",
            "revision": 1,
            "confirmed_at": None,
        }
    )
    service.session(session_id).proposals["proposal-unknown"] = proposal

    with pytest.raises(ValueError, match="Units must be resolved"):
        service.confirm_spec(
            session_id=session_id,
            proposal_id="proposal-unknown",
            edits=None,
            expected_revision=1,
        )


def test_confirm_spec_with_missing_stock_dimension_raises(service):
    """Missing stock dimensions must be caught."""
    session_id = service.new_session_id()

    proposal = DEMO_SPEC.model_copy(
        update={
            "stock_z_mm": None,
            "proposal_id": "proposal-missing",
            "revision": 1,
            "confirmed_at": None,
        }
    )
    service.session(session_id).proposals["proposal-missing"] = proposal

    with pytest.raises(ValueError, match="Still missing: stock_z_mm"):
        service.confirm_spec(
            session_id=session_id,
            proposal_id="proposal-missing",
            edits=None,
            expected_revision=1,
        )


def test_confirm_spec_with_missing_material_raises(service):
    """Missing material must be caught."""
    session_id = service.new_session_id()

    proposal = DEMO_SPEC.model_copy(
        update={
            "material": "",
            "proposal_id": "proposal-no-mat",
            "revision": 1,
            "confirmed_at": None,
        }
    )
    service.session(session_id).proposals["proposal-no-mat"] = proposal

    with pytest.raises(ValueError, match="Still missing: material"):
        service.confirm_spec(
            session_id=session_id,
            proposal_id="proposal-no-mat",
            edits=None,
            expected_revision=1,
        )


def test_confirm_spec_with_proposal_from_another_session_raises(service):
    """A proposal ID from another session must be denied."""
    s1 = service.new_session_id()
    s2 = service.new_session_id()

    proposal = DEMO_SPEC.model_copy(
        update={"proposal_id": "proposal-other", "revision": 1, "confirmed_at": None}
    )
    service.session(s1).proposals["proposal-other"] = proposal

    with pytest.raises(AccessDenied, match="Unknown proposal for this session"):
        service.confirm_spec(
            session_id=s2, proposal_id="proposal-other", edits=None, expected_revision=1
        )


# -----------------------------------------------------------------------------
# REVISE SPEC AND RUN JOB
# -----------------------------------------------------------------------------


async def test_revise_spec_bumps_revision(service, confirmed_spec):
    """Revising a spec must increment the revision number."""
    session_id = service.new_session_id()
    service.session(session_id).specs["spec-1"] = confirmed_spec

    revised = service.revise_spec(
        session_id=session_id, spec=confirmed_spec, edits={"stock_z_mm": 25.0}
    )

    assert revised.revision == confirmed_spec.revision + 1
    assert revised.stock_z_mm == 25.0


async def test_run_job_with_stale_spec_revision_raises_conflict(service, confirmed_spec):
    """A stale expected_spec_revision must raise ConflictError."""
    session_id = service.new_session_id()
    service.session(session_id).specs["spec-1"] = confirmed_spec

    revised = service.revise_spec(
        session_id=session_id, spec=confirmed_spec, edits={"stock_z_mm": 25.0}
    )

    # Try to run with the old revision
    request = RunRequest(
        session_id=session_id,
        spec=revised,
        shop=DEMO_SHOP,
        expected_spec_revision=confirmed_spec.revision,
    )

    with pytest.raises(
        ConflictError, match="specification was edited after this run was requested"
    ):
        async for _ in service.run_job(request):
            pass


# -----------------------------------------------------------------------------
# IDEMPOTENCY
# -----------------------------------------------------------------------------


async def test_idempotency_same_key_replays_first_job(service, confirmed_spec):
    """Two run_job calls with the same idempotency_key must produce ONE job."""
    session_id = service.new_session_id()
    key = "idempotent-run-1"

    request = RunRequest(
        session_id=session_id,
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        idempotency_key=key,
    )

    # First run
    events1 = [event async for event in service.run_job(request)]
    job_id1 = events1[0].job_id

    # Second run with same key
    events2 = [event async for event in service.run_job(request)]
    job_id2 = events2[0].job_id

    # Must be the same job
    assert job_id1 == job_id2
    # Events must be replayed, not new
    assert len(events1) == len(events2)
    # Verify sequence numbers match (replayed)
    for e1, e2 in zip(events1, events2, strict=False):
        assert e1.sequence == e2.sequence
        assert e1.type == e2.type


async def test_idempotency_different_keys_produce_different_jobs(service, confirmed_spec):
    """Different idempotency_keys must produce different jobs."""
    session_id = service.new_session_id()

    request1 = RunRequest(
        session_id=session_id,
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        idempotency_key="key-1",
    )
    request2 = RunRequest(
        session_id=session_id,
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        idempotency_key="key-2",
    )

    events1 = [event async for event in service.run_job(request1)]
    events2 = [event async for event in service.run_job(request2)]

    job_id1 = events1[0].job_id
    job_id2 = events2[0].job_id

    assert job_id1 != job_id2


# -----------------------------------------------------------------------------
# ONE ACTIVE JOB PER SESSION
# -----------------------------------------------------------------------------


async def test_second_concurrent_job_raises_conflict(service, confirmed_spec):
    """Starting a second concurrent job must raise ConflictError."""
    session_id = service.new_session_id()

    # Start first job (but don't complete it)
    request1 = RunRequest(
        session_id=session_id,
        spec=confirmed_spec,
        shop=DEMO_SHOP,
        budget=Budget(job_deadline_s=600),
    )
    async_iter1 = service.run_job(request1).__aiter__()
    await async_iter1.__anext__()  # Get first event, job is now active

    # Try to start second job
    request2 = RunRequest(
        session_id=session_id,
        spec=confirmed_spec,
        shop=DEMO_SHOP,
    )

    with pytest.raises(ConflictError, match="already has a job running"):
        async for _ in service.run_job(request2):
            pass


# -----------------------------------------------------------------------------
# ADD ASSET VALIDATION
# -----------------------------------------------------------------------------


def test_add_asset_rejects_unsupported_mime(service):
    """add_asset must reject unsupported MIME types."""
    session_id = service.new_session_id()

    with pytest.raises(ValueError, match="Unsupported file type"):
        service.add_asset(session_id, "evil.exe", b"MZ\x90\x00", "application/x-msdownload")


def test_add_asset_rejects_empty_upload(service):
    """add_asset must reject empty uploads."""
    session_id = service.new_session_id()

    with pytest.raises(ValueError, match="Empty upload"):
        service.add_asset(session_id, "empty.png", b"", "image/png")


def test_add_asset_rejects_oversize_upload(service):
    """add_asset must reject uploads exceeding MAX_UPLOAD_BYTES."""
    session_id = service.new_session_id()
    huge_data = b"x" * (MAX_UPLOAD_BYTES + 1)

    with pytest.raises(ValueError, match="limit is"):
        service.add_asset(session_id, "huge.png", huge_data, "image/png")


def test_add_asset_hostile_filename_never_becomes_path(service):
    """A hostile display_filename must never become a storage path."""
    session_id = service.new_session_id()
    hostile_names = [
        "../../etc/passwd",
        "../../../root/.ssh/id_rsa",
        "..\\..\\windows\\system32\\config\\sam",
        "/etc/shadow",
        "C:\\Windows\\System32\\calc.exe",
    ]

    for hostile in hostile_names:
        asset = service.add_asset(session_id, hostile, b"safe data", "image/png")

        # The asset_id must be a generated UUID, not derived from the filename
        assert asset.asset_id.startswith("asset-")
        assert len(asset.asset_id) == len("asset-") + 12  # UUID hex prefix

        # The display filename must be sanitized (only basename)
        assert ".." not in asset.display_filename
        assert "/" not in asset.display_filename
        assert "\\" not in asset.display_filename

        # The stored data must be retrievable by asset_id, proving it wasn't
        # stored at a hostile path
        session = service.session(session_id)
        assert session.asset_bytes[asset.asset_id] == b"safe data"


def test_add_asset_stores_correct_hash(service):
    """add_asset must compute correct SHA-256."""
    session_id = service.new_session_id()
    data = b"test image data"
    expected_hash = hashlib.sha256(data).hexdigest()

    asset = service.add_asset(session_id, "test.png", data, "image/png")

    assert asset.sha256 == expected_hash
    assert asset.byte_length == len(data)
