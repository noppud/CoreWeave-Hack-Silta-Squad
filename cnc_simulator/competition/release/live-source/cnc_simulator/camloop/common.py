import copy
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from cncsim.geometry import InputError, keys, number
from cncsim.simulator import validate


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def load_job(path):
    path = Path(path).resolve()
    job = json.loads(path.read_text())
    keys(
        job,
        ["id", "plan", "family", "feature", "feed_limits_mm_min", "max_moves"],
        ["final_position"],
    )
    if job["family"] not in ("capsule_pocket", "pocket_set"):
        raise InputError("Loop supports capsule_pocket and pocket_set feature descriptions")
    features = [job["feature"]]
    if job["family"] == "pocket_set":
        keys(job["feature"], ["pockets"])
        features = job["feature"]["pockets"]
        if not isinstance(features, list) or not 1 <= len(features) <= 20:
            raise InputError("pocket_set requires 1..20 pockets")
    for feature in features:
        keys(feature, ["centerline_start", "centerline_end", "radius", "floor_z", "stock_top_z"])
        for field in ("radius", "floor_z", "stock_top_z"):
            number(feature[field], field, positive=field == "radius")
        for field in ("centerline_start", "centerline_end"):
            if not isinstance(feature[field], list) or len(feature[field]) != 2:
                raise InputError("Feature centerline endpoints must be XY pairs")
            for value in feature[field]:
                number(value, field)
        if feature["floor_z"] >= feature["stock_top_z"]:
            raise InputError("Pocket floor must be below stock top")
    if type(job["max_moves"]) is not int or not 1 <= job["max_moves"] <= 500:
        raise InputError("max_moves must be in [1,500]")
    if "final_position" in job:
        from cncsim.geometry import vector

        vector(job["final_position"], "final_position")
    plan_path = (path.parent / job["plan"]).resolve()
    plan = json.loads(plan_path.read_text())
    validate(plan)
    for spec in [plan["target"], plan["stock"]] + plan["fixtures"]:
        if spec["type"] == "mesh":
            spec["path"] = str((plan_path.parent / spec["path"]).resolve(strict=True))
    if set(job["feed_limits_mm_min"]) != set(plan["tools"]):
        raise InputError("Every tool requires a fixed feed limit")
    for limit in job["feed_limits_mm_min"].values():
        number(limit, "feed limit", positive=True)
    job["plan"] = plan
    return job


def freeze_job(job, directory):
    job = copy.deepcopy(job)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    mesh_hashes = {}
    for i, spec in enumerate(
        [job["plan"]["target"], job["plan"]["stock"]] + job["plan"]["fixtures"]
    ):
        if spec["type"] == "mesh":
            source = Path(spec["path"])
            dest = directory / f"geometry-{i}{source.suffix}"
            shutil.copyfile(source, dest)
            spec["path"] = str(dest.resolve())
            mesh_hashes[str(dest.resolve())] = file_hash(dest)
    save(directory / "job.json", job)
    return job, dict(job=digest(job), meshes=mesh_hashes)


def verify_frozen(job, fingerprint):
    if digest(job) != fingerprint["job"] or any(
        file_hash(p) != h for p, h in fingerprint["meshes"].items()
    ):
        raise InputError("Frozen target or manufacturing inputs changed")


def candidate(job, proposal):
    keys(proposal, ["summary", "moves"])
    if not isinstance(proposal["summary"], str) or not isinstance(proposal["moves"], list):
        raise InputError("Planner must return summary and movement array")
    for move in proposal["moves"]:
        keys(move, ["type"], ["to", "feed_mm_per_min", "seconds", "tool"])
    moves = [{k: v for k, v in move.items() if v is not None} for move in proposal["moves"]]
    plan = copy.deepcopy(job["plan"])
    plan["moves"] = moves
    validate(plan)
    return plan


def cheap_checks(job, plan, rules=()):
    validate(plan)
    issues = []
    if {k: v for k, v in plan.items() if k != "moves"} != {
        k: v for k, v in job["plan"].items() if k != "moves"
    }:
        raise InputError("Candidate changed fixed manufacturing contract")
    if not plan["moves"] or len(plan["moves"]) > job["max_moves"]:
        issues.append(
            dict(code="move_budget", moves=[], description="Plan must contain 1..max_moves moves")
        )
    if "final_position" in job:
        final = next(
            (m["to"] for m in reversed(plan["moves"]) if "to" in m), plan["initial_position"]
        )
        if any(abs(a - b) > 1e-8 for a, b in zip(final, job["final_position"], strict=True)):
            issues.append(
                dict(
                    code="final_position",
                    moves=[],
                    description=(
                        "Return to the fixed final XYZ position; approach and retract are part of "
                        "every comparable cycle"
                    ),
                )
            )
    tool = plan["initial_tool"]
    for i, move in enumerate(plan["moves"]):
        if move["type"] == "tool_change":
            tool = move["tool"]
        if move["type"] == "cut" and move["feed_mm_per_min"] > job["feed_limits_mm_min"][tool]:
            issues.append(
                dict(
                    code="feed_limit", moves=[i], description=f"Feed exceeds fixed limit for {tool}"
                )
            )
        if "to" in move and any(
            x < lo or x > hi
            for x, lo, hi in zip(
                move["to"], plan["travel_limits"]["min"], plan["travel_limits"]["max"], strict=True
            )
        ):
            issues.append(
                dict(
                    code="axis_overtravel",
                    moves=[i],
                    description="Move exceeds fixed travel limits",
                )
            )
        for rule in rules:
            if rule["name"] == "feature_floor" and rule["family"] == job["family"]:
                # Linear segments attain min Z at an endpoint; initial position
                # and all earlier endpoints also need checking for the cut start.
                start = (
                    plan["initial_position"]
                    if i == 0
                    else next(
                        (m["to"] for m in reversed(plan["moves"][:i]) if "to" in m),
                        plan["initial_position"],
                    )
                )
                if move["type"] != "cut" or plan["stock"]["type"] != "box":
                    continue
                a, b = (
                    np.array(job["feature"][k], dtype=float)
                    for k in ("centerline_start", "centerline_end")
                )
                delta = b - a
                for endpoint in (start, move["to"]):
                    xy = np.array(endpoint[:2])
                    along = (
                        0
                        if np.dot(delta, delta) == 0
                        else np.clip(np.dot(xy - a, delta) / np.dot(delta, delta), 0, 1)
                    )
                    in_feature = np.linalg.norm(xy - a - along * delta) <= job["feature"]["radius"]
                    inside_stock_xy = all(
                        lo + plan["tolerance_mm"] < pos < hi - plan["tolerance_mm"]
                        for pos, lo, hi in zip(
                            xy, plan["stock"]["min"][:2], plan["stock"]["max"][:2], strict=True
                        )
                    )
                    reaches_stock = (
                        endpoint[2] + plan["tools"][tool]["flute_length_mm"]
                        > plan["stock"]["min"][2] + plan["tolerance_mm"]
                    )
                    if (
                        in_feature
                        and inside_stock_xy
                        and reaches_stock
                        and endpoint[2] < job["feature"]["floor_z"] - plan["tolerance_mm"]
                    ):
                        issues.append(
                            dict(
                                code="learned_feature_floor",
                                moves=[i],
                                description=(
                                    "Pocket-floor check: cutter enters required material "
                                    "below the floor"
                                ),
                            )
                        )
                        break
    return issues
