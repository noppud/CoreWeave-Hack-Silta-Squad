"""Test CAD building, STEP export and verification against independent oracle."""

import math
import tempfile
from pathlib import Path

import pytest

from silta.cad import build_and_export, verify_against_oracle
from silta.fixtures import DEMO_SPEC, expected_geometry


@pytest.mark.slow
class TestCadBuilding:
    """CAD tests are slow due to CadQuery import time (~2s warm)."""

    def test_built_solid_matches_independent_oracle(self):
        """The volume and bbox must match the analytic oracle from fixtures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_and_export(DEMO_SPEC, Path(tmpdir))
            oracle = expected_geometry()

            # Check using the independent verification function
            checks = verify_against_oracle(result, oracle)

            # All checks must pass
            for name, passed, detail in checks:
                assert passed, f"{name} failed: {detail}"

    def test_step_reimport_matches_built_volume(self):
        """The STEP file must reimport to the same volume."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_and_export(DEMO_SPEC, Path(tmpdir))

            # Reimported volume must match original within tolerance
            assert math.isclose(result.reimported_volume_mm3, result.volume_mm3, rel_tol=1e-3), (
                f"STEP roundtrip mismatch: {result.reimported_volume_mm3} vs {result.volume_mm3}"
            )

    def test_build_is_deterministic(self):
        """Building the same spec twice must produce identical results."""
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            result1 = build_and_export(DEMO_SPEC, Path(tmpdir1))
            result2 = build_and_export(DEMO_SPEC, Path(tmpdir2))

            # Volume, bbox and hashes must match
            assert math.isclose(result1.volume_mm3, result2.volume_mm3, rel_tol=1e-9)
            assert result1.bbox_mm == result2.bbox_mm
            # Note: STEP hash can vary due to timestamps, but volume must not

    def test_cad_files_exported(self):
        """Both STEP and STL files must be created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_and_export(DEMO_SPEC, Path(tmpdir))

            assert result.step_path.exists()
            assert result.mesh_path.exists()
            assert result.step_path.suffix == ".step"
            assert result.mesh_path.suffix == ".stl"

            # Files must have content
            assert result.step_path.stat().st_size > 0
            assert result.mesh_path.stat().st_size > 0

    def test_solid_valid_flag(self):
        """The solid_valid flag must be True for a valid spec."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_and_export(DEMO_SPEC, Path(tmpdir))
            assert result.solid_valid is True


@pytest.mark.slow
def test_build_runs_from_a_worker_thread(tmp_path):
    """The controller builds CAD in a thread; the deployed service failed only there.

    CadQuery string selectors are parsed by pyparsing, which infers a parse action's
    arity by introspecting a traceback. Built first inside a worker thread under an
    instrumented runtime, it settled on the wrong arity and the deployed service raised
    "atom_callback() missing 1 required positional argument: 'res'" while the identical
    image succeeded on the main thread. Exercise the threaded path explicitly.
    """
    import concurrent.futures

    from silta.cad import build_and_export, verify_against_oracle
    from silta.fixtures import DEMO_SPEC, expected_geometry

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(build_and_export, DEMO_SPEC, tmp_path / "threaded").result()

    for name, ok, detail in verify_against_oracle(result, expected_geometry()):
        assert ok, f"{name}: {detail}"
