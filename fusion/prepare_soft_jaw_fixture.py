"""Prepare the pinned Haas vise in G54 coordinates; does not certify workholding.

Run apply(app, payload) in Fusion's main thread. Imports a fresh fixture-only
copy. Never edits the accepted part or the source archive. Units inside Fusion
are centimetres; report distances are millimetres.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

SOURCE_SHA256 = "003fca01f919e859989c74e653045a48dde94aa6175fe56c380e04748330ecd6"
MOVING = {5, 7, 8, 14, 15}
FIXED = set(range(1, 18)) - MOVING
SLOT_CENTRES_CM = (-1.937 * 2.54, 1.938 * 2.54)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _xyz(point):
    return [point.x, point.y, point.z]


def _bounds(body):
    box = body.boundingBox
    return [_xyz(box.minPoint), _xyz(box.maxPoint)]


def _plane_faces(body, axis, coordinate, core):
    faces = []
    for face in body.faces:
        plane = core.Plane.cast(face.geometry)
        if plane is None:
            continue
        bounds = _bounds(face)
        if abs(abs(_xyz(plane.normal)[axis]) - 1) < 1e-7 and all(
            abs(b[axis] - coordinate) < 1e-5 for b in bounds
        ):
            faces.append(face)
    return sorted(faces, key=lambda f: f.area, reverse=True)


def _box(manager, core, low, high):
    box = core.OrientedBoundingBox3D.create(
        core.Point3D.create(*[(a + b) / 2 for a, b in zip(low, high, strict=True)]),
        core.Vector3D.create(1, 0, 0),
        core.Vector3D.create(0, 1, 0),
        *[b - a for a, b in zip(low, high, strict=True)],
    )
    body = manager.createBox(box)
    if body is None:
        raise RuntimeError("Could not construct temporary measurement envelope")
    return body


def _overlap(manager, fusion, one, two):
    a, b = _bounds(one), _bounds(two)
    if any(min(a[1][i], b[1][i]) - max(a[0][i], b[0][i]) <= 1e-7 for i in range(3)):
        return {"status": "clear", "method": "disjoint bounding boxes", "overlap_mm3": 0}
    result = manager.copy(one)
    if not manager.booleanOperation(result, two, fusion.BooleanTypes.IntersectionBooleanType):
        return {"status": "unknown", "reason": "BRep intersection operation failed"}
    volume = result.volume * 1000
    return {
        "status": "clear" if volume < 1e-6 else "overlap",
        "method": "BRep intersection",
        "overlap_mm3": volume,
    }


def _suppress_pose_constraints(root):
    """Suppress the imported copy's solvers before setting independent rigid poses."""
    report = []
    confirmed_groups = set()
    # Suppress joints first so rigid-group edits cannot drag the second assembly.
    for kind, collection in (
        ("as_built_joint", root.asBuiltJoints),
        ("joint", root.joints),
        ("rigid_group", root.rigidGroups),
    ):
        for constraint in collection:
            record = {
                "kind": kind,
                "name": constraint.name,
                "originally_suppressed": constraint.isSuppressed,
            }
            if kind == "rigid_group":
                members = [occ.name for occ in constraint.occurrences]
                record["members"] = members
                if "Component5:1" in members:
                    expected = {f"Component{i}:1" for i in MOVING}
                    if set(members) != expected:
                        raise RuntimeError(
                            "Actual moving rigid group contradicts prepared grouping"
                        )
                    confirmed_groups.add("moving")
                elif "Component10:1" in members:
                    expected = {f"Component{i}:1" for i in FIXED}
                    if set(members) != expected:
                        raise RuntimeError("Actual fixed rigid group contradicts prepared grouping")
                    confirmed_groups.add("fixed")
            constraint.isSuppressed = True
            if not constraint.isSuppressed:
                raise RuntimeError(f"Could not suppress imported {kind}: {constraint.name}")
            record["now_suppressed"] = True
            report.append(record)
    if confirmed_groups != {"moving", "fixed"}:
        raise RuntimeError("Both actual source rigid groups must confirm prepared grouping")
    return report


def _readback_poses(occurrences, expected, before):
    """Check all poses after all writes, catching later solver propagation."""
    actual = {}
    for i, occurrence in occurrences.items():
        pose = list(occurrence.transform2.asArray())
        if any(abs(a - b) > 1e-7 for a, b in zip(pose, expected[str(i)], strict=True)):
            raise RuntimeError(f"Component{i} rigid pose changed after assembly placement")
        if abs(occurrence.bRepBodies.item(0).volume - before[i]["volume_cm3"]) > 1e-6:
            raise RuntimeError(f"Component{i} volume changed during rigid placement")
        actual[str(i)] = pose
    return actual


def apply(app, payload):
    """payload: config_path, output_directory (new), optional preview bool."""
    import adsk.core as core
    import adsk.fusion as fusion

    config_path = Path(payload["config_path"]).resolve()
    config = json.loads(config_path.read_text())
    fixture = config["setup"]["fixture"]
    source = Path(fixture["artifact"]["path"])
    if _sha(source) != SOURCE_SHA256 or fixture["artifact"]["sha256"] != SOURCE_SHA256:
        raise ValueError("This helper only supports the exact inspected Haas 05-0404 archive")
    if fixture["jaw_opening_mm"] != 50.8 or fixture["clamp_depth_mm"] != 6.35:
        raise ValueError("Unexpected fixture dimensions; rederive placement")
    if config["setup"]["stock"]["dimensions_mm"] != [152.4, 50.8, 25.4]:
        raise ValueError("Unexpected stock dimensions")
    output = Path(payload["output_directory"]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    document = app.importManager.importToNewDocument(
        app.importManager.createFusionArchiveImportOptions(str(source))
    )
    if document is None:
        raise RuntimeError("Fresh fixture import failed")
    design = next((fusion.Design.cast(p) for p in document.products if fusion.Design.cast(p)), None)
    if design is None:
        raise RuntimeError("Imported fixture has no design")
    root = design.rootComponent
    if root.bRepBodies.count or root.occurrences.count != 17:
        raise RuntimeError("Unexpected source assembly; refusing inferred component grouping")
    occurrences = {i: root.occurrences.itemByName(f"Component{i}:1") for i in range(1, 18)}
    identity = core.Matrix3D.create()
    for i, occurrence in occurrences.items():
        if (
            occurrence is None
            or not occurrence.transform2.isEqualTo(identity)
            or occurrence.bRepBodies.count != 1
        ):
            raise RuntimeError(f"Unexpected source occurrence {i}")
    before = {
        i: {"bounds_cm": _bounds(o.bRepBodies.item(0)), "volume_cm3": o.bRepBodies.item(0).volume}
        for i, o in occurrences.items()
    }
    fixed_body, moving_body = occurrences[10].bRepBodies.item(0), occurrences[5].bRepBodies.item(0)
    left, right = before[10]["bounds_cm"][1][0], before[5]["bounds_cm"][0][0]
    if abs(right - left - 22.86) > 1e-4:
        raise RuntimeError("Unexpected initial 228.6mm jaw opening")
    fixed_faces = _plane_faces(fixed_body, 0, left, core)
    moving_faces = _plane_faces(moving_body, 0, right, core)
    if not moving_faces or not fixed_faces:
        raise RuntimeError("Actual planar gripping faces were not found")
    moving_face, fixed_face = moving_faces[0], fixed_faces[0]
    jaw_top = min(_bounds(moving_face)[1][2], _bounds(fixed_face)[1][2])
    jaw_y_center = sum(_bounds(fixed_face)[j][1] for j in (0, 1)) / 2
    shift = 5.08 - (right - left)
    jaw_x_center = left + 2.54
    support = payload.get("supports")
    support_bed_raw = None
    if support:
        if support.get("dimensions_mm") != [152.4, 12.7, 38.1]:
            raise ValueError("Only explicitly selected Haas 09-0108 6x0.5x1.5in supports supported")
        if support.get("source_url") != "https://www.haastooling.com/p/09-0108":
            raise ValueError("Support provenance must be the selected vendor page")
        # The top horizontal surface of the actual base supplies the Z reference.
        base = occurrences[1].bRepBodies.item(0)
        planes = _plane_faces(base, 2, _bounds(base)[1][2], core)
        if not planes:
            raise RuntimeError("Cannot identify the actual base top support plane")
        support_bed_raw = _bounds(planes[0])[1][2]
        z_shift = -2.54 - 3.81 - support_bed_raw
    else:
        z_shift = -1.905 - jaw_top
    constraint_changes = _suppress_pose_constraints(root)
    grounding_changes = []
    for i, occurrence in occurrences.items():
        if occurrence.isGrounded:
            occurrence.isGrounded = False
            if occurrence.isGrounded:
                raise RuntimeError(f"Could not unground imported Component{i}")
            grounding_changes.append(i)
    # Rotate +90 degrees around Z, then place gripping faces at Y +/-25.4mm.
    transforms = {}
    for i, occurrence in occurrences.items():
        matrix = core.Matrix3D.create()
        shift_i = shift if i in MOVING else 0
        matrix.setWithArray(
            [0, -1, 0, jaw_y_center, 1, 0, 0, shift_i - jaw_x_center, 0, 0, 1, z_shift, 0, 0, 0, 1]
        )
        occurrence.transform2 = matrix
        transforms[str(i)] = list(matrix.asArray())
        if abs(occurrence.bRepBodies.item(0).volume - before[i]["volume_cm3"]) > 1e-6:
            raise RuntimeError("Rigid placement unexpectedly changed fixture volume")
    if design.designType == fusion.DesignTypes.ParametricDesignType:
        if design.snapshots.hasPendingSnapshot and design.snapshots.add() is None:
            raise RuntimeError("Could not capture rigid fixture positions")
    transforms = _readback_poses(occurrences, transforms, before)
    actual_contacts = {}
    for index, y in ((10, -2.54), (5, 2.54)):
        faces = _plane_faces(occurrences[index].bRepBodies.item(0), 1, y, core)
        if not faces:
            raise RuntimeError("Actual jaw face did not reach intended clamping coordinate")
        low, high = _bounds(faces[0])
        actual_contacts[str(index)] = {
            "face_bounds_mm": [[v * 10 for v in p] for p in (low, high)],
            "vertical_stock_overlap_mm": max(0, min(0, high[2]) - max(-2.54, low[2])) * 10,
            "stock_length_overlap_mm": max(0, min(7.62, high[0]) - max(-7.62, low[0])) * 10,
        }
    manager = fusion.TemporaryBRepManager.get()
    stock = _box(manager, core, [-7.62, -2.54, -2.54], [7.62, 2.54, 0])
    # Conservative rectangular envelopes around the exact through obrounds:
    # 0.510in width, 0.120in straight segment; 3.875in centre spacing.
    envelopes = [
        _box(manager, core, [x - 0.6477, -0.8001, -2.64], [x + 0.6477, 0.8001, 0.001])
        for x in SLOT_CENTRES_CM
    ]
    measurements = []
    bed_faces = []
    for i, occurrence in occurrences.items():
        body = occurrence.bRepBodies.item(0)
        measurements.append(
            {
                "component": i,
                "bounds_mm": [[v * 10 for v in p] for p in _bounds(body)],
                "stock": _overlap(manager, fusion, stock, body),
                "slot_envelopes": [_overlap(manager, fusion, e, body) for e in envelopes],
            }
        )
        if i in (1, 9):
            for face in body.faces:
                plane = core.Plane.cast(face.geometry)
                if plane and abs(abs(plane.normal.z) - 1) < 1e-7:
                    low, high = _bounds(face)
                    if (
                        high[2] < -2.54
                        and high[0] > -7.62
                        and low[0] < 7.62
                        and high[1] > -2.54
                        and low[1] < 2.54
                    ):
                        bed_faces.append(
                            {
                                "component": i,
                                "face_area_mm2": face.area * 100,
                                "face_bounds_mm": [[v * 10 for v in p] for p in (low, high)],
                                "required_support_height_mm": (-2.54 - high[2]) * 10,
                            }
                        )
    bed_faces.sort(key=lambda f: f["required_support_height_mm"])
    support_report = None
    if support:
        supports = []
        for index, y_limits in enumerate(((-2.54, -1.27), (1.27, 2.54)), start=1):
            envelope = _box(manager, core, [-7.62, y_limits[0], -6.35], [7.62, y_limits[1], -2.54])
            collision = [
                {
                    "component": i,
                    **_overlap(manager, fusion, envelope, occurrence.bRepBodies.item(0)),
                }
                for i, occurrence in occurrences.items()
            ]
            # Measure actual material under the parallel's footprint using a 0.1mm
            # layer below the bed. This is coverage evidence, not a force analysis.
            probe = _box(manager, core, [-7.62, y_limits[0], -6.36], [7.62, y_limits[1], -6.350001])
            support_coverage = _overlap(manager, fusion, probe, occurrences[1].bRepBodies.item(0))
            support_occurrence = root.occurrences.addNewComponent(core.Matrix3D.create())
            support_occurrence.component.name = f"Haas 09-0108 parallel envelope {index}"
            if design.designType == fusion.DesignTypes.ParametricDesignType:
                feature = support_occurrence.component.features.baseFeatures.add()
                feature.startEdit()
                body = support_occurrence.component.bRepBodies.add(envelope, feature)
                feature.finishEdit()
            else:
                body = support_occurrence.component.bRepBodies.add(envelope)
            if body is None:
                raise RuntimeError("Parallel envelope insertion failed")
            supports.append(
                {
                    "bounds_mm": [[v * 10 for v in p] for p in _bounds(body)],
                    "fixture_overlap": collision,
                    "slot_envelopes": [_overlap(manager, fusion, e, envelope) for e in envelopes],
                    "bed_probe_volume_mm3": probe.volume * 1000,
                    "bed_material_overlap": support_coverage,
                }
            )
        support_report = {
            "source_url": support["source_url"],
            "dimensions_mm": support["dimensions_mm"],
            "representation": "Conservative solid boxes; vendor drilled holes omitted",
            "actual_base_top_raw_mm": support_bed_raw * 10,
            "derived_clamp_depth_mm": (jaw_top + z_shift + 2.54) * 10,
            "supports": supports,
            "status": "geometry_inserted_requires_contact_review",
        }
    transforms = _readback_poses(occurrences, transforms, before)
    archive = output / "haas-vise-50p8mm-g54.f3d"
    if not design.exportManager.execute(
        design.exportManager.createFusionArchiveExportOptions(str(archive))
    ):
        raise RuntimeError("Prepared fixture export failed")
    report = {
        "status": "fixture_positioned_contact_review_required",
        "source": {"path": str(source), "sha256": SOURCE_SHA256},
        "configuration_sha256": _sha(config_path),
        "fixture": {"path": str(archive), "sha256": _sha(archive)},
        "coordinate_frame": "G54 stock top centre; X long edge, Y clamp direction, Z upward",
        "movable_components": sorted(MOVING),
        "constraint_changes": constraint_changes,
        "ungrounded_components": grounding_changes,
        "assembly_mode": "Static fixture copy; source constraints suppressed, geometry unchanged",
        "grouping_basis": (
            "Actual source RigidGroup2: moving jaw5 and components7,8,14,15; "
            "RigidGroup1: fixed base1 and jaw10. Slider3 joins7 to1."
        ),
        "raw_jaw_shift_mm": shift * 10,
        "occurrence_transforms_cm": transforms,
        "derived_gripping_face_top_raw_mm": jaw_top * 10,
        "nominal_jaw_opening_mm": 50.8,
        "derived_vertical_contact_mm": (jaw_top + z_shift + 2.54) * 10,
        "support_report": support_report,
        "actual_gripping_faces": actual_contacts,
        "actual_body_measurements": measurements,
        "potential_support_bed_faces": bed_faces,
        "support_exclusion_xy_mm": [
            {"x": [x - 6.477, x + 6.477], "y": [-8.001, 8.001]}
            for x in (c * 10 for c in SLOT_CENTRES_CM)
        ],
        "possible_support_xy_regions_mm": {
            "x_outside_slots": [
                [-76.2, SLOT_CENTRES_CM[0] * 10 - 6.477],
                [SLOT_CENTRES_CM[0] * 10 + 6.477, SLOT_CENTRES_CM[1] * 10 - 6.477],
                [SLOT_CENTRES_CM[1] * 10 + 6.477, 76.2],
            ],
            "y_outside_slots": [[-25.4, -8.001], [8.001, 25.4]],
        },
        "remaining": [
            "No supports present. Inspect actual bed-face boundaries before adding supports.",
            "Supports must fit continuous bed lands outside the slot and breakthrough envelopes.",
            "Machine table placement, attachment and kinematics remain unverified.",
            "Contact patches, clamp forces and jaw deflection remain unverified.",
        ],
        "manufacturing_verified": False,
    }
    if support:
        report["remaining"] = [
            "Review parallel-to-base contact coverage and fixture overlap before acceptance.",
            "Parallels use conservative envelopes from vendor dimensions; drilled holes omitted.",
            "Machine attachment, clamp force and cutting load verification remain unresolved.",
        ]
    if payload.get("preview", True):
        app.activeViewport.fit()
        preview = output / "fixture.png"
        if app.activeViewport.saveAsImageFile(str(preview), 1600, 1200):
            report["preview"] = {"path": str(preview), "sha256": _sha(preview)}
    report_path = output / "fixture-report.json"
    report_path.write_text(json.dumps(report, indent=2))
    return {"report": str(report_path), **report}
