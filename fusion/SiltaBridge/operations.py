"""Small explicit Fusion API surface. Called only on Fusion's main thread."""
import hashlib
import json
from pathlib import Path

import adsk.core
import adsk.fusion
import adsk.cam

_generation = None


def _items(collection):
    return [collection.item(i) for i in range(collection.count)]


def _cam(app):
    if not app.activeDocument:
        raise RuntimeError("No active document")
    cam = adsk.cam.CAM.cast(app.activeDocument.products.itemByProductType("CAMProductType"))
    if not cam:
        raise RuntimeError("Active document has no CAM product; create a manufacturing setup first")
    return cam


def _design(app):
    if not app.activeDocument:
        raise RuntimeError("No active document")
    products = _items(app.activeDocument.products)
    design = next((d for p in products if (d := adsk.fusion.Design.cast(p))), None)
    if not design:
        raise RuntimeError("Active document has no design")
    return design


def _artifact(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _inspect(app):
    result = {"fusion_version": app.version,
              "document": app.activeDocument.name if app.activeDocument else None}
    if not app.activeDocument:
        return result
    products = _items(app.activeDocument.products)
    design = next((d for p in products if (d := adsk.fusion.Design.cast(p))), None)
    if design:
        result["bodies"] = [{"name": b.name, "volume_cm3": b.volume,
                             "bounding_box_cm": {"min": b.boundingBox.minPoint.asArray(),
                                                 "max": b.boundingBox.maxPoint.asArray()}}
                            for b in _items(design.rootComponent.bRepBodies)]
    cam = next((c for p in products if (c := adsk.cam.CAM.cast(p))), None)
    if cam:
        operations = [adsk.cam.Operation.cast(op) for op in _items(cam.allOperations)]
        result["operations"] = [{"id": str(op.operationId), "name": op.name,
                                 "has_toolpath": op.hasToolpath,
                                 "tool": json.loads(op.tool.toJson()) if op.tool else None}
                                for op in operations if op]
        result["setups"] = [{"name": s.name, "id": str(s.operationId)} for s in _items(cam.setups)]
        result["nc_programs"] = [{"name": p.name, "index": i}
                                 for i, p in enumerate(_items(cam.ncPrograms))]
    return result


def dispatch(app, action, payload):
    global _generation
    if action == "ping":
        return {"result": {"fusion_version": app.version,
                           "document": app.activeDocument.name if app.activeDocument else None}}
    if action == "inspect":
        return {"result": _inspect(app)}
    if action == "run_script":
        source = payload["source"]
        # This is authorized CAD/CAM code, not an isolation boundary.
        ui = app.userInterface
        if ui.activeCommand != "SelectCommand":
            ui.commandDefinitions.itemById("SelectCommand").execute()
        namespace = {"app": app, "adsk": adsk, "payload": payload.get("arguments", {}),
                     "result": None, "__name__": "__silta_script__"}
        exec(compile(source, "<silta-cad-cam-script>", "exec"), namespace)
        json.dumps(namespace["result"])  # Require a portable structured return value.
        return {"result": namespace["result"], "coverage": ["script_execution_only"]}
    if action == "open_cad":
        path = Path(payload["path"]).resolve(strict=True)
        manager = app.importManager
        if path.suffix.lower() in (".step", ".stp"):
            options = manager.createSTEPImportOptions(str(path))
        elif path.suffix.lower() == ".f3d":
            options = manager.createFusionArchiveImportOptions(str(path))
        else:
            raise ValueError("open_cad supports STEP and F3D")
        document = manager.importToNewDocument(options)
        if not document:
            raise RuntimeError("Fusion import failed")
        return {"result": {"document": document.name, "source": _artifact(path)}}
    if action in ("export_step", "export_f3d"):
        path = Path(payload["path"]).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        design = _design(app)
        manager = design.exportManager
        options = (manager.createSTEPExportOptions(str(path)) if action == "export_step"
                   else manager.createFusionArchiveExportOptions(str(path)))
        if not manager.execute(options):
            raise RuntimeError("Fusion export returned false")
        return {"result": _artifact(path), "evidence": [str(path)]}
    if action == "generate_toolpaths":
        _generation = _cam(app).generateAllToolpaths(bool(payload.get("skip_valid", True)))
        return {"completed": False, "result": {"generation_started": True}}
    if action == "generation_status":
        if _generation is None:
            raise RuntimeError("No generation started through this bridge")
        done = _generation.isGenerationCompleted
        return {"completed": done, "result": {"generation_completed": done},
                "coverage": ["toolpath_generation_only"]}
    if action == "machining_time":
        cam = _cam(app)
        collection = adsk.core.ObjectCollection.create()
        for setup in _items(cam.setups):
            collection.add(setup)
        # Do not invent machine rates; callers supply actual assumptions.
        time = cam.getMachiningTime(collection, float(payload["feed_scale_percent"]),
                                   float(payload["rapid_feed_cm_s"]), float(payload["tool_change_seconds"]))
        metrics = {"machining_seconds": time.machiningTime, "feed_seconds": time.totalFeedTime,
                   "rapid_seconds": time.totalRapidTime, "tool_change_seconds": time.totalToolChangeTime,
                   "tool_change_count": time.toolChangeCount,
                   "feed_distance_cm": time.feedDistance, "rapid_distance_cm": time.rapidDistance}
        return {"metrics": metrics, "result": {"assumptions": payload},
                "coverage": ["internal_cam_time_estimate"]}
    if action == "postprocess":
        program = _cam(app).ncPrograms.item(int(payload["program_index"]))
        if not program:
            raise ValueError("NC program does not exist")
        if not program.postConfiguration:
            raise ValueError("NC program must have an explicitly selected post configuration")
        output = Path(payload["output_directory"]).resolve()
        output.mkdir(parents=True, exist_ok=True)
        if any(output.iterdir()):
            raise ValueError("Use an empty unique output directory so stale NC cannot be accepted")
        parameters = program.parameters
        parameters.itemByName("nc_program_output_folder").value.value = str(output)
        parameters.itemByName("nc_program_openInEditor").value.value = False
        if not program.postProcess(adsk.cam.NCProgramPostProcessOptions.create()):
            raise RuntimeError("Fusion postprocessing returned false")
        return {"completed": not app.hasActiveJobs,
                "result": {"output_directory": str(output), "active_jobs": app.hasActiveJobs},
                "coverage": ["postprocessing_only"]}
    if action == "collect_outputs":
        if app.hasActiveJobs:
            return {"completed": False, "result": {"active_jobs": True}}
        paths = sorted(p for p in Path(payload["output_directory"]).resolve().rglob("*") if p.is_file())
        if not paths:
            raise RuntimeError("No output files produced")
        return {"result": {"files": [_artifact(p) for p in paths]}, "evidence": [str(p) for p in paths],
                "coverage": ["exported_files_only"]}
    if action == "command_inventory":
        return {"result": {"commands": [{"id": c.id, "name": c.name}
                                          for c in _items(app.userInterface.commandDefinitions)
                                          if any(s in (c.id + c.name).lower()
                                                 for s in ("simulat", "verif", "collis"))]}}
    if action == "simulation":
        return {"status": "unknown", "completed": False, "coverage": [],
                "issues": [{"type": "needs_ui_verification", "message":
                            "No established milling verification results API. Capture completed Fusion UI verification for this candidate and setup."}],
                "result": _inspect(app)}
    raise ValueError("Unsupported Fusion action: " + action)
