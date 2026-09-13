"""Post diagnostic evidence against the already active exact saved candidate.

Default prepares a request only; --execute submits once through SiltaBridge.
Never opens/saves a document, generates paths, or changes the existing NC program.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def binding(document):
    data = document.dataFile
    if data is None:
        raise ValueError("Active document is not saved")
    return dict(
        data_file_id=data.id,
        version_id=data.versionId,
        version_number=data.versionNumber,
        project_id=data.parentProject.id,
        document_name=document.name,
        is_modified=document.isModified,
    )


def require_binding(actual, expected):
    for key in ("data_file_id", "version_id", "version_number", "project_id"):
        if key not in expected or actual[key] != expected[key]:
            raise ValueError("Active document binding mismatch: " + key)
    if actual["is_modified"]:
        raise ValueError("Diagnostic requires unmodified pinned active document")


def post(app, payload):
    import adsk.cam

    document = app.activeDocument
    if document is None or app.hasActiveJobs:
        raise ValueError("Requires active document with no running Fusion job")
    before = binding(document)
    require_binding(before, payload["reference"])
    cam = adsk.cam.CAM.cast(document.products.itemByProductType("CAMProductType"))
    setup = cam.setups.item(payload["setup_index"]) if cam else None
    if setup is None or setup.name != payload["setup_name"]:
        raise ValueError("Selected setup does not match exact expected name/index")
    operations = []
    for base in setup.allOperations:
        op = adsk.cam.Operation.cast(base)
        if op and not op.isSuppressed:
            if not op.hasToolpath or not op.isToolpathValid:
                raise ValueError("All selected operations require existing valid toolpaths")
            operations.append(op)
    if not operations:
        raise ValueError("No selected operations")
    cps = Path(payload["cps_path"])
    if hashlib.sha256(cps.read_bytes()).hexdigest() != payload["cps_sha256"]:
        raise ValueError("Diagnostic CPS changed after request preparation")
    output = Path(payload["output_directory"])
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(
        before=before,
        setup_name=setup.name,
        setup_index=payload["setup_index"],
        operations=[dict(id=o.operationId, name=o.name) for o in operations],
        cps_sha256=payload["cps_sha256"],
        completed=False,
    )
    program = None
    nc_count = cam.ncPrograms.count
    try:
        config = adsk.cam.PostConfiguration.createFromContent(cps.read_text())
        if config is None:
            raise RuntimeError("Diagnostic post configuration unavailable")
        inp = cam.ncPrograms.createInput()
        inp.displayName = "Silta temporary frame diagnostic"
        inp.operations = operations
        program = cam.ncPrograms.add(inp)
        if program is None:
            raise RuntimeError("Temporary NC program creation failed")
        program.postConfiguration = config
        for name, value in [
            ("nc_program_output_folder", str(output)),
            ("nc_program_openInEditor", False),
        ]:
            program.parameters.itemByName(name).value.value = value
        actual_post = program.parameters.itemByName("nc_program_post").value.value
        if hashlib.sha256(Path(actual_post).read_bytes()).hexdigest() != payload["cps_sha256"]:
            raise RuntimeError("Resolved post bytes mismatch")
        options = adsk.cam.NCProgramPostProcessOptions.create()
        options.postProcessExecutionBehavior = (
            adsk.cam.PostProcessExecutionBehaviors.PostProcessExecutionBehavior_Fail
        )
        receipt["post_returned"] = program.postProcess(options)
        receipt["active_jobs_after_post"] = app.hasActiveJobs
        receipt["completed"] = receipt["post_returned"] is True and not app.hasActiveJobs
    except Exception as exc:
        receipt["error"] = str(exc)
    finally:
        if program is not None:
            try:
                program.deleteMe()
            except Exception as exc:
                receipt["cleanup_error"] = str(exc)
        receipt["after"] = binding(document)
        receipt["temporary_program_removed"] = cam.ncPrograms.count == nc_count
        receipt["active_document_unchanged"] = app.activeDocument == document
        receipt["requires_reopen_before_verification"] = document.isModified
        receipt["completed"] = (
            receipt["completed"]
            and receipt["temporary_program_removed"]
            and receipt["active_document_unchanged"]
        )
        receipt["files"] = [
            dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            for p in output.iterdir()
            if p.is_file()
        ]
        Path(payload["receipt_path"]).write_text(json.dumps(receipt, indent=2))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference",
        required=True,
        type=Path,
        help="JSON containing exact saved-document reference",
    )
    parser.add_argument("--setup-index", type=int, default=0)
    parser.add_argument("--setup-name", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    cps = ROOT / "fusion/operation_frames.cps"
    payload = dict(
        reference=json.loads(args.reference.read_text()),
        setup_index=args.setup_index,
        setup_name=args.setup_name,
        cps_path=str(cps),
        cps_sha256=hashlib.sha256(cps.read_bytes()).hexdigest(),
        output_directory=str(args.output.resolve() / "post"),
        receipt_path=str(args.output.resolve() / "receipt.json"),
    )
    source = (
        f"import runpy\nresult = runpy.run_path({str(Path(__file__).resolve())!r})"
        "['post'](app, payload)"
    )
    request = dict(source=source, arguments=payload)
    (args.output / "request.json").write_text(json.dumps(request, indent=2))
    if args.execute:
        sys.path.insert(0, str(ROOT))
        from silta.cnc.fusion import FusionBridge

        response = FusionBridge().request("run_script", request, timeout=180)
        (args.output / "bridge-response.json").write_text(json.dumps(response, indent=2))
        print(json.dumps(response, indent=2))
    else:
        print("Prepared only: " + str(args.output / "request.json"))


if __name__ == "__main__":
    main()
