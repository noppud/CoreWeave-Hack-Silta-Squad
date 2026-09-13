"""Deterministic Fusion camera framing. Presentation only; no CAM/geometry edits."""

import math


def frame(app, payload):
    if payload.get("action") == "orbit":
        return orbit(app, payload)

    import adsk.core

    document = app.activeDocument
    if document is None or document.name != payload["document"]:
        raise RuntimeError("Presentation camera requires the exact active document")
    viewport = app.activeViewport
    camera = viewport.camera
    before = {
        "eye_cm": list(camera.eye.asArray()),
        "target_cm": list(camera.target.asArray()),
        "up": list(camera.upVector.asArray()),
        "type": int(camera.cameraType),
    }
    action = payload.get("action", "inspect")
    if action == "frame":
        target = payload["target_mm"]
        eye = payload["eye_mm"]
        span = payload["height_mm"]
        if (
            len(target) != 3
            or len(eye) != 3
            or not all(math.isfinite(v) for v in [*target, *eye, span])
            or span <= 0
        ):
            raise ValueError("Camera requires finite positions and positive view height")
        camera.cameraType = adsk.core.CameraTypes.OrthographicCameraType
        camera.target = adsk.core.Point3D.create(*(v / 10 for v in target))
        camera.eye = adsk.core.Point3D.create(*(v / 10 for v in eye))
        camera.upVector = adsk.core.Vector3D.create(0, 0, 1)
        camera.isSmoothTransition = False
        camera.isFitView = False
        if not camera.setExtents(span / 10, span / 10):
            raise RuntimeError("Camera extent could not be set")
        viewport.camera = camera
        viewport.refresh()
    elif action == "fit":
        viewport.fit()
        viewport.refresh()
    elif action != "inspect":
        raise ValueError("Unknown camera action")
    after = viewport.camera
    result = {
        "document": document.name,
        "before": before,
        "eye_cm": list(after.eye.asArray()),
        "target_cm": list(after.target.asArray()),
        "extents_cm": list(after.getExtents()),
        "presentation_only": True,
    }
    if payload.get("image_path"):
        result["saved"] = viewport.saveAsImageFile(payload["image_path"], 1920, 1080)
        if not result["saved"]:
            raise RuntimeError("Viewport image capture failed")
    return result


def orbit_parameters(payload):
    """Validate all orbit inputs before accessing or changing a Fusion viewport."""

    def scalar(name, default, lower, upper):
        value = payload.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be finite numeric")
        if not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f"{name} must be within {lower}..{upper}")
        return float(value)

    target = payload.get("target_mm", [0, 0, 195])
    if not isinstance(target, (list, tuple)) or len(target) != 3:
        raise ValueError("target_mm requires three finite coordinates")
    if any(
        isinstance(v, bool)
        or not isinstance(v, (int, float))
        or not math.isfinite(v)
        or abs(v) > 100000
        for v in target
    ):
        raise ValueError("target_mm requires finite bounded coordinates")
    params = {
        "target_mm": list(target),
        "seconds": scalar("seconds", 16, 5, 30),
        "radius_mm": scalar("radius_mm", 380, 1, 100000),
        "eye_z_mm": scalar("eye_z_mm", 430, -100000, 100000),
        "height_mm": scalar("height_mm", 210, 1, 100000),
        "start_angle_degrees": scalar("start_angle_degrees", -60, -360, 360),
        "sweep_degrees": scalar("sweep_degrees", 360, -360, 360),
    }
    if params["sweep_degrees"] == 0:
        raise ValueError("sweep_degrees must be nonzero")
    if not isinstance(payload.get("document"), str) or not payload["document"].strip():
        raise ValueError("Exact document name is required")
    return params


def orbit_pose(parameters, progress):
    """Quintic ease-in/out gives zero endpoint velocity and acceleration."""
    progress = max(0.0, min(1.0, progress))
    eased = progress**3 * (10 + progress * (-15 + 6 * progress))
    angle = math.radians(parameters["start_angle_degrees"] + parameters["sweep_degrees"] * eased)
    target = parameters["target_mm"]
    return [
        target[0] + parameters["radius_mm"] * math.cos(angle),
        target[1] + parameters["radius_mm"] * math.sin(angle),
        parameters["eye_z_mm"],
    ]


def _document_identity(app, expected_name):
    document = app.activeDocument
    if document is None or document.name != expected_name:
        raise RuntimeError("Camera orbit lost the exact active document")
    data_file = document.dataFile
    if data_file is None:
        raise RuntimeError("Camera orbit requires a saved document identity")
    return {
        "name": document.name,
        "data_file_id": data_file.id,
        "version_number": data_file.versionNumber,
    }


def orbit(app, payload):
    """One main-thread camera request; 60 Hz is a schedule, not delivered video FPS."""
    parameters = orbit_parameters(payload)

    import time

    import adsk
    import adsk.core
    identity = _document_identity(app, payload["document"])
    viewport = app.activeViewport
    before = {
        "eye_cm": list(viewport.camera.eye.asArray()),
        "target_cm": list(viewport.camera.target.asArray()),
    }
    trajectory = []
    start = time.perf_counter()
    next_deadline = start
    error = None
    try:
        while True:
            if _document_identity(app, payload["document"]) != identity:
                raise RuntimeError("Camera orbit document identity changed")
            elapsed = time.perf_counter() - start
            progress = min(elapsed / parameters["seconds"], 1.0)
            eye = orbit_pose(parameters, progress)
            camera = viewport.camera
            camera.cameraType = adsk.core.CameraTypes.OrthographicCameraType
            camera.target = adsk.core.Point3D.create(*(v / 10 for v in parameters["target_mm"]))
            camera.eye = adsk.core.Point3D.create(*(v / 10 for v in eye))
            camera.upVector = adsk.core.Vector3D.create(0, 0, 1)
            camera.isSmoothTransition = False
            camera.isFitView = False
            if not camera.setExtents(parameters["height_mm"] / 10, parameters["height_mm"] / 10):
                raise RuntimeError("Camera orbit extent could not be set")
            viewport.camera = camera
            viewport.refresh()
            adsk.doEvents()
            # Recheck after event dispatch, which can process a user's document switch.
            if _document_identity(app, payload["document"]) != identity:
                raise RuntimeError("Camera orbit document identity changed")
            observed = viewport.camera
            trajectory.append(
                {
                    "elapsed_seconds": time.perf_counter() - start,
                    "progress": progress,
                    "eye_cm": list(observed.eye.asArray()),
                    "target_cm": list(observed.target.asArray()),
                }
            )
            if progress >= 1:
                break
            next_deadline = max(next_deadline + 1 / 60, time.perf_counter())
            remaining = next_deadline - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
    except Exception as exc:
        error = str(exc)
    duration = time.perf_counter() - start
    return {
        "status": "interrupted" if error else "completed",
        "error": error,
        "document_identity": identity,
        "parameters": parameters,
        "before": before,
        "duration_seconds": duration,
        "requested_update_hz": 60,
        "actual_update_count": len(trajectory),
        "trajectory": trajectory,
        "observed_update_hz": (len(trajectory) - 1) / duration if duration else 0,
        "presentation_only": True,
        "verification_pass": False,
        "fps_note": "Camera update timestamps; video frame delivery is measured by recorder",
    }
