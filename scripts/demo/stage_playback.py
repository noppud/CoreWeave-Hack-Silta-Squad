"""Presentation-only playback after a completed verdict; never verification."""

import json
import time
from pathlib import Path

_BIND = """
import adsk.cam
reference = payload['reference']
doc = app.activeDocument
data = doc.dataFile if doc else None
if data is None or any(
    getattr(data, attr) != reference[key]
    for attr,key in [('id','data_file_id'),('versionId','version_id'),
                     ('versionNumber','version_number')]
):
    raise RuntimeError('Presentation candidate document/version changed')
if data.parentProject.id != reference['project_id'] or app.hasActiveJobs:
    raise RuntimeError('Presentation project changed or Fusion job active')
cam = adsk.cam.CAM.cast(doc.products.itemByProductType('CAMProductType'))
if cam is None or cam.setups.count != 1:
    raise RuntimeError('Presentation requires exactly one retained setup')
result = {'document':doc.name, 'setup_ids':[str(cam.setups.item(0).operationId)]}
"""

_DISPLAY = (
    _BIND
    + """
import adsk.fusion
design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
if design is None:
    raise RuntimeError('Presentation target design missing')
root = design.rootComponent
bodies = [root.bRepBodies.item(i) for i in range(root.bRepBodies.count)]
for occurrence in root.allOccurrences:
    bodies.extend(occurrence.bRepBodies.item(i) for i in range(occurrence.bRepBodies.count))
targets = {}
for body in bodies:
    native = body.nativeObject or body
    attribute = native.attributes.itemByName('silta', 'accepted_target_body')
    if attribute:
        if not attribute.value or attribute.value in targets:
            raise RuntimeError('Presentation target identity ambiguous')
        targets[attribute.value] = body
if not targets:
    raise RuntimeError('Presentation accepted target bodies missing')
before = {key: bool(body.isLightBulbOn) for key,body in targets.items()}
action = payload['display_action']
if action not in ('inspect', 'hide', 'restore'):
    raise ValueError('Unknown presentation display action')
if action != 'inspect':
    saved = payload['states']
    if set(saved) != set(targets) or any(type(value) is not bool for value in saved.values()):
        raise RuntimeError('Presentation target display snapshot does not match')
    desired = {key: False for key in targets} if action == 'hide' else saved
    if action == 'hide' and before != saved:
        raise RuntimeError('Target display changed before presentation')
    try:
        for key,body in targets.items():
            body.isLightBulbOn = desired[key]
        if any(bool(body.isLightBulbOn) != desired[key] for key,body in targets.items()):
            raise RuntimeError('Target display change not observed')
    except Exception:
        for key,body in targets.items():
            body.isLightBulbOn = before[key]
        raise
result = {'document':doc.name, 'scope':'accepted target body display only; fixtures untouched',
          'action':action, 'states_before':before,
          'states_after':{key:bool(body.isLightBulbOn) for key,body in targets.items()}}
"""
)


def dismiss_observed_marking_menu(native):
    """Dismiss only an actually observed native menu; never send blind Escape."""
    before = native.ui("inspect")
    observed = any(w.get("title") == "Marking Menu" for w in before.get("windows", []))
    evidence = {
        "menu_observed": observed,
        "escape_sent": False,
        "windows_before": before.get("windows", []),
    }
    if observed:
        evidence["escape_sent"] = True
        native.ui("key", "escape")
        after = native.ui("inspect")
        evidence["windows_after"] = after.get("windows", [])
        evidence["menu_still_open"] = any(
            w.get("title") == "Marking Menu" for w in after.get("windows", [])
        )
    return evidence


def show(candidate, bridge, directory, seconds=15, *, playback_factory=None, wait=time.sleep):
    from silta.cnc.simulation_video import FusionPlayback, playback_position

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    row = {
        "meaning": "Presentation playback after completed verification; not a new verdict",
        "candidate_id": candidate.id,
        "status": "not_started",
        "machine_tool_visibility": (
            "Presenter must establish both in Fusion Display before rehearsal; "
            "not automatically verified"
        ),
    }
    playback = None
    launched = False
    reference = None
    display_states = None
    started = time.monotonic()
    try:
        candidate.verify()
        cloud = candidate.artifacts.get("fusion_document")
        if cloud is None:
            raise ValueError("Presentation requires saved cloud candidate")
        reference = json.loads(Path(cloud.path).read_text())
        reply = bridge.request(
            "run_script", {"source": _BIND, "arguments": {"reference": reference}}
        )
        if reply.get("status") != "ok":
            raise RuntimeError("Presentation binding failed: " + str(reply.get("error")))
        binding = reply["result"]
        row["binding"] = binding
        inspected = bridge.request(
            "run_script",
            {
                "source": _DISPLAY,
                "arguments": {"reference": reference, "display_action": "inspect"},
            },
        )
        if inspected.get("status") != "ok":
            raise RuntimeError("Presentation target display inspection failed")
        display_states = inspected["result"]["states_before"]
        row["target_display_before"] = inspected["result"]
        hidden = bridge.request(
            "run_script",
            {
                "source": _DISPLAY,
                "arguments": {
                    "reference": reference,
                    "display_action": "hide",
                    "states": display_states,
                },
            },
        )
        if hidden.get("status") != "ok":
            raise RuntimeError("Presentation target display hide failed")
        row["target_display_hidden"] = hidden["result"]
        launched = True  # Failed command reply can still leave simulation open.
        launch = bridge.request(
            "simulation_command",
            {"command_id": "IronMachineSimulation", "setup_ids": binding["setup_ids"]},
        )
        if launch.get("status") != "ok":
            raise RuntimeError("Presentation launch failed")
        # Fixed presentation view for this demo's UMC750 and tall pedestal.
        camera = bridge.request(
            "presentation_camera",
            {
                "document": binding["document"],
                "action": "frame",
                "target_mm": [0, 0, 230],
                "eye_mm": [900, -1300, 1000],
                "height_mm": 850,
            },
        )
        if camera.get("status") != "ok":
            raise RuntimeError("Presentation camera framing failed")
        row["camera"] = camera.get("result", {})
        playback_position(bridge.request("simulation_dialog"), binding["document"])
        playback = (playback_factory or FusionPlayback)(
            binding["document"], directory / "ui", bridge
        )
        playback.prepare()
        row["position_before"] = playback_position(
            bridge.request("simulation_dialog"), binding["document"]
        )
        playback.start()
        row["playback_requested"] = True
        row["tool_motion_observed"] = False
        row["status"] = "playback_requested"
        wait(seconds)
        row["position_after"] = playback_position(
            bridge.request("simulation_dialog"), binding["document"]
        )
        row["tool_motion_observed"] = (
            row["position_before"]["tool_position"] != row["position_after"]["tool_position"]
        )
        row["status"] = (
            "tool_motion_observed"
            if row["tool_motion_observed"]
            else "playback_requested_motion_not_observed"
        )
    except Exception as exc:
        row.update(status="presentation_failed", error=str(exc))
    finally:
        if playback:
            try:
                playback.stop()
            except Exception as exc:
                row["stop_error"] = str(exc)
                try:
                    row["stop_menu_cleanup"] = dismiss_observed_marking_menu(playback.native)
                except Exception as cleanup_error:
                    row["stop_menu_cleanup_error"] = str(cleanup_error)
        if launched:
            try:
                row["simulation_stop"] = bridge.request(
                    "simulation_command", {"command_id": "SimulationStop"}
                )
            except Exception as exc:
                row["simulation_stop_error"] = str(exc)
        if display_states is not None:
            try:
                restored = bridge.request(
                    "run_script",
                    {
                        "source": _DISPLAY,
                        "arguments": {
                            "reference": reference,
                            "display_action": "restore",
                            "states": display_states,
                        },
                    },
                )
                row["target_display_restore"] = restored
                if restored.get("status") != "ok":
                    raise RuntimeError("Target display restoration failed")
                if restored["result"]["states_after"] != display_states:
                    raise RuntimeError("Target display restoration mismatch")
            except Exception as exc:
                row["target_display_restore_error"] = str(exc)
                row["status"] = "presentation_failed"
        if (
            row.get("stop_error")
            or row.get("simulation_stop_error")
            or row.get("simulation_stop", {}).get("status", "ok") != "ok"
        ):
            row["status"] = "presentation_failed"
        row["presentation_wall_seconds"] = time.monotonic() - started
        (directory / "presentation-playback.json").write_text(json.dumps(row, indent=2))
    return row
