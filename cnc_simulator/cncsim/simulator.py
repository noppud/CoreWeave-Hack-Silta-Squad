"""Conservative voxel stock removal. This module has no service or desktop dependencies."""

import hashlib
import json
from pathlib import Path

import numpy as np

from .indexing import validate_indexing, world_points, index_samples
from .geometry import InputError, Solid, keys, number, sweep, vector, voxel_mesh


def validate(plan):
    keys(
        plan,
        [
            "units",
            "target",
            "stock",
            "tools",
            "fixtures",
            "travel_limits",
            "initial_position",
            "initial_tool",
            "moves",
            "tolerance_mm",
            "resolution_mm",
            "rapid_mm_per_min",
            "tool_change_seconds",
        ],
        ["max_cells", "indexing"],
    )
    if "indexing" in plan:
        validate_indexing(plan["indexing"])
    if plan["units"] != "mm":
        raise InputError("Only millimetres are supported")
    for field in ["tolerance_mm", "resolution_mm", "rapid_mm_per_min"]:
        number(plan[field], field, positive=True)
    number(plan["tool_change_seconds"], "tool_change_seconds", nonnegative=True)
    max_cells = plan.get("max_cells", 2_000_000)
    if (
        isinstance(max_cells, bool)
        or not isinstance(max_cells, int)
        or not 1 <= max_cells <= 20_000_000
    ):
        raise InputError("max_cells must be an integer in [1, 20000000]")
    keys(plan["travel_limits"], ["min", "max"])
    lo, hi = (vector(plan["travel_limits"][k], k) for k in ["min", "max"])
    if np.any(lo >= hi):
        raise InputError("Travel limits must have positive extents")
    if not isinstance(plan["tools"], dict) or not plan["tools"]:
        raise InputError("tools must be a nonempty tool-ID mapping")
    fields = [
        "diameter_mm",
        "flute_length_mm",
        "shaft_diameter_mm",
        "shaft_length_mm",
        "holder_diameter_mm",
        "holder_length_mm",
    ]
    for name, tool in plan["tools"].items():
        if not isinstance(name, str):
            raise InputError("Tool IDs must be strings")
        keys(tool, fields)
        for field in fields:
            number(tool[field], f"{name}.{field}", positive=True)
    if not isinstance(plan["fixtures"], list) or not isinstance(plan["moves"], list):
        raise InputError("fixtures and moves must be lists")
    if plan["initial_tool"] not in plan["tools"]:
        raise InputError("Unknown initial_tool")
    position = vector(plan["initial_position"], "initial_position")
    tool_id = plan["initial_tool"]
    steps, timing = [], dict(cutting=0.0, rapid=0.0, dwell=0.0, tool_changes=0.0)
    bc = np.array(plan.get("indexing", {}).get("initial_bc_degrees", [0,0]), dtype=float)
    if "indexing" in plan:
        timing["indexing"] = 0.0
    for index, move in enumerate(plan["moves"]):
        if not isinstance(move, dict):
            raise InputError(f"Move {index} must be an object")
        kind = move.get("type")
        end = position.copy()
        if kind in ("cut", "rapid"):
            keys(move, ["type", "to"] + (["feed_mm_per_min"] if kind == "cut" else []))
            end = vector(move["to"], f"move {index}.to")
            speed = number(
                move["feed_mm_per_min"] if kind == "cut" else plan["rapid_mm_per_min"],
                "speed",
                positive=True,
            )
            seconds = float(np.linalg.norm(end - position)) / speed * 60
            timing["cutting" if kind == "cut" else "rapid"] += seconds
        elif kind == "index":
            if "indexing" not in plan:
                raise InputError("index requires indexing configuration")
            keys(move, ["type", "b_degrees", "c_degrees"])
            next_bc = np.array([number(move[k], k) for k in ["b_degrees", "c_degrees"]])
            if np.max(np.abs(next_bc - bc)) > 2000:
                raise InputError("Index exceeds bounded rotation range")
            seconds = float(np.max(np.abs(next_bc - bc))) / plan["indexing"]["degrees_per_second"] + plan["indexing"]["settle_seconds"]
            timing["indexing"] += seconds
            bc = next_bc
        elif kind == "dwell":
            keys(move, ["type", "seconds"])
            seconds = number(move["seconds"], "dwell seconds", nonnegative=True)
            timing["dwell"] += seconds
        elif kind == "tool_change":
            keys(move, ["type", "tool"])
            if move["tool"] not in plan["tools"]:
                raise InputError(f"Move {index}: unknown tool")
            tool_id = move["tool"]
            seconds = plan["tool_change_seconds"]
            timing["tool_changes"] += seconds
        else:
            raise InputError(
                f"Move {index}: unsupported movement {kind!r}; no G-code dialect is supported"
            )
        if not np.isfinite(seconds):
            raise InputError("Movement duration overflow")
        steps.append((index, kind, position.copy(), end.copy(), tool_id, seconds))
        position = end
    if not np.isfinite(sum(timing.values())):
        raise InputError("Total duration overflow")
    return steps, timing


def simulate(plan, *, base_dir=".", output_dir=None, on_step=None, snapshot_stride=1):
    """Return JSON-compatible results; optionally export artifacts and stream stock states.

    on_step(state) receives independent arrays at initial state (move=-1) and every
    move boundary. States contain origin, pitch, shape, lower/upper/nominal occupancy,
    position, tool ID, elapsed time and move index. Inputs are never modified.
    Invalid input raises InputError; unresolved discretization fails verification.
    """
    if isinstance(snapshot_stride, bool) or not isinstance(snapshot_stride, int) or snapshot_stride < 1:
        raise InputError("snapshot_stride must be a positive integer")
    steps, timing = validate(plan)
    result = {
        "validity": "invalid",
        "passed": False,
        "verification": "unresolved",
        "issues": [],
        "estimated_time_seconds": sum(timing.values()),
        "time_breakdown": timing,
        "timing_assumptions": "Constant commanded vector feed/rapid speed; no acceleration, jerk, "
        "lookahead, spindle ramp or controller blending. Cut includes air cutting "
        "and plunge/retract. Tool changes add fixed duration, with no implicit travel. "
        "Full submitted plan timed even if invalid.",
    }
    if "indexing" in plan:
        result["timing_assumptions"] += " Indexed B/C rotation uses simultaneous constant angular speeds plus settle time. No cutting during indexing."
        result["scope"] = "Indexed 3+2 only; table-attached stock and fixtures. Tool-section collision and configured axis limits; whole-machine self-collision is not certified. Gauge length is fixed across tools."
    issues = result["issues"]

    def issue(code, certainty, move, description):
        issues.append(dict(code=code, certainty=certainty, moves=move, description=description))

    target = Solid(plan["target"], base_dir, mesh_only=True)
    target_path = Path(base_dir) / plan["target"]["path"]
    result["target_sha256"] = hashlib.sha256(target_path.read_bytes()).hexdigest()
    stock = Solid(plan["stock"], base_dir)
    fixtures = [Solid(s, base_dir) for s in plan["fixtures"]]
    bounds = np.array([s.bounds for s in [target, stock] + fixtures])
    pitch = float(plan["resolution_mm"])
    origin = np.floor(bounds[:, 0].min(axis=0) / pitch) * pitch - pitch
    extent = np.ceil((bounds[:, 1].max(axis=0) - origin) / pitch) + 1
    cell_count = float(np.prod(extent))
    if not np.isfinite(cell_count) or cell_count > plan.get("max_cells", 2_000_000):
        issue(
            "resource_limit",
            "uncertain",
            [],
            "Geometry grid exceeds max_cells; reduce bounds or increase resolution_mm.",
        )
        return result
    shape = tuple(int(x) for x in extent)
    points = origin + (np.indices(shape).reshape(3, -1).T + 0.5) * pitch
    scale = max(1.0, float(np.abs(bounds).max()), float(np.abs(points).max()))
    guard = max(1e-7, scale * 1e-12)
    rho = np.sqrt(3) * pitch / 2 + guard
    lower, upper, nominal = stock.occupancy(points, pitch, guard)
    index_spec = plan.get("indexing")
    bc = np.array(index_spec["initial_bc_degrees"] if index_spec else [0,0], dtype=float)
    query_points = world_points(points, bc, index_spec) if index_spec else points
    initial_nominal = nominal.copy()
    initial_lower, initial_upper = lower.copy(), upper.copy()
    target_d = target.signed(points)
    if not np.isfinite(target_d).all():
        issue(
            "geometry_query",
            "uncertain",
            [],
            "Nonfinite target distance; no geometry verdict possible.",
        )
        return result
    fixture_cells = [f.occupancy(points, pitch, guard)[:2] for f in fixtures]
    result["numerics"] = dict(
        resolution_mm=pitch,
        cell_radius_mm=rho,
        cells=len(points),
        geometry_backend="trimesh signed distance; double precision, not exact arithmetic",
    )
    travel_lo = np.array(plan["travel_limits"]["min"])
    travel_hi = np.array(plan["travel_limits"]["max"])
    snapshots, poses = [], []
    elapsed = 0.0
    output = Path(output_dir) if output_dir is not None else None
    if output:
        source_specs = [plan["target"], plan["stock"]] + plan["fixtures"]
        source_paths = {
            (Path(base_dir) / spec["path"]).resolve()
            for spec in source_specs
            if spec["type"] == "mesh"
        }
        if any(path.is_relative_to(output.resolve()) for path in source_paths):
            raise InputError(
                "Output directory must not contain input meshes; use a separate directory"
            )
        destinations = [
            output / name
            for name in [
                "final_stock.ply",
                "final_stock_lower.ply",
                "final_stock_upper.ply",
                "trajectory.json",
                "result.json",
            ]
        ]
        destinations += [output / "states" / f"{i:05d}.npz" for i in range(len(steps) + 1)]
        if any(path.resolve() in source_paths for path in destinations):
            raise InputError("Output path aliases an input mesh")
        output.mkdir(parents=True, exist_ok=True)
        (output / "states").mkdir(exist_ok=True)

    def emit(index, position, tool_id, start=None, kind="initial"):
        state = dict(
            move=index,
            bc_degrees=bc.tolist(),
            position=position.tolist(),
            tool=tool_id,
            elapsed_seconds=elapsed,
            origin=origin.tolist(),
            pitch=pitch,
            shape=list(shape),
        )
        if output:
            poses.append(
                {**state, "type": kind, "from": (start if start is not None else position).tolist()}
            )
        if on_step:
            on_step(
                {**state, "lower": lower.copy(), "upper": upper.copy(), "nominal": nominal.copy()}
            )
        if output and (index == -1 or index == len(steps)-1 or (index+1) % snapshot_stride == 0):
            filename = f"states/{index + 1:05d}.npz"
            np.savez_compressed(
                output / filename,
                lower=lower.reshape(shape),
                upper=upper.reshape(shape),
                nominal=nominal.reshape(shape),
                origin=origin,
                pitch=pitch,
                position=position,
                tool=tool_id,
                move=index,
                elapsed_seconds=elapsed,
            )
            snapshots.append(filename)

    def contact(a, b, radius, z0, z1):
        return (sweep(query_points, a, b, radius, z0, z1, -rho), sweep(query_points, a, b, radius, z0, z1, rho))

    def check_contact(code, index, swept, occupancy, description, subtract=None):
        inside, possible = swept
        solid_lo, solid_hi = occupancy
        certain = inside & solid_lo
        maybe = possible & solid_hi
        # A cut may clear stock earlier within this move. Only prove a noncutting
        # collision where even the possible cutter sweep cannot clear that stock.
        if subtract is not None:
            certain &= ~subtract
        if np.any(certain):
            issue(code, "definite", [index], description)
        elif np.any(maybe):
            issue(
                code,
                "uncertain",
                [index],
                description + " (within discretization/contact uncertainty)",
            )

    def run_move(index, kind, a, b, tool_id):
        nonlocal lower, upper, nominal
        machine_a, machine_b = a.copy(), b.copy()
        if index_spec:
            mount = np.array(index_spec["head_mount_mm"])
            gauge = np.array([0,0,index_spec["gauge_length_mm"]])
            machine_a, machine_b = a + gauge - mount, b + gauge - mount
            if not index_spec["b_limits_degrees"][0] <= bc[0] <= index_spec["b_limits_degrees"][1]:
                issue("axis_overtravel", "definite", [index], "B table angle exceeds configured limits.")
        if (
            np.any(machine_a < travel_lo)
            or np.any(machine_a > travel_hi)
            or np.any(machine_b < travel_lo)
            or np.any(machine_b > travel_hi)
        ):
            issue(
                "axis_overtravel",
                "definite",
                [index],
                "Tool-tip path exceeds configured XYZ travel limits.",
            )
        tool = plan["tools"][tool_id]
        flute = tool["flute_length_mm"]
        shaft_end = flute + tool["shaft_length_mm"]
        sections = [
            ("cutter", tool["diameter_mm"] / 2, 0, flute),
            ("shaft", tool["shaft_diameter_mm"] / 2, flute, shaft_end),
            (
                "holder",
                tool["holder_diameter_mm"] / 2,
                shaft_end,
                shaft_end + tool["holder_length_mm"],
            ),
        ]
        cutting = contact(a, b, sections[0][1], 0, flute)
        for label, radius, z0, z1 in sections:
            swept = cutting if label == "cutter" else contact(a, b, radius, z0, z1)
            for j, fixture in enumerate(fixture_cells):
                check_contact(
                    "fixture_collision", index, swept, fixture, f"{label} intersects fixture {j}."
                )
            if label != "cutter":
                check_contact(
                    "noncutting_stock_collision",
                    index,
                    swept,
                    (lower, upper),
                    f"{label} intersects stock.",
                    cutting[1] if kind == "cut" else None,
                )
            elif kind in ("rapid", "initial", "tool_change"):
                check_contact(
                    "rapid_through_stock" if kind == "rapid" else "tool_placement_collision",
                    index,
                    swept,
                    (lower, upper),
                    "Noncutting movement/placement of cutter intersects stock.",
                )
        if kind == "cut":
            cut_lo, cut_hi = cutting
            tol = plan["tolerance_mm"]
            if np.any(cut_lo & lower & (target_d > tol + rho)):
                issue(
                    "gouge",
                    "definite",
                    [index],
                    "Cut removes target material deeper than tolerance.",
                )
            elif np.any(cut_hi & upper & (target_d > tol - rho)):
                issue("gouge", "uncertain", [index], "Possible removal of target beyond tolerance.")
            lower &= ~cut_hi
            upper &= ~cut_lo
            nominal &= ~sweep(query_points, a, b, sections[0][1], 0, flute)

    position = np.array(plan["initial_position"], dtype=float)
    run_move(-1, "initial", position, position, plan["initial_tool"])
    emit(-1, position, plan["initial_tool"])
    for index, kind, a, b, tool_id, seconds in steps:
        if kind == "index":
            move = plan["moves"][index]
            next_bc = np.array([move["b_degrees"], move["c_degrees"]])
            tool = plan["tools"][tool_id]
            flute = tool["flute_length_mm"]
            shaft = flute + tool["shaft_length_mm"]
            sections = [(tool["diameter_mm"]/2,0,flute), (tool["shaft_diameter_mm"]/2,flute,shaft), (tool["holder_diameter_mm"]/2,shaft,shaft+tool["holder_length_mm"])]
            # During indexing the tool is stationary and no stock may be removed.
            for sample, motion_guard in index_samples(points, bc, next_bc, index_spec):
                for radius, z0, z1 in sections:
                    swept = (sweep(sample,a,a,radius,z0,z1,-rho-motion_guard), sweep(sample,a,a,radius,z0,z1,rho+motion_guard))
                    check_contact("index_stock_collision",index,swept,(lower,upper),"Rotating stock may contact stationary tool.")
                    for j, fixture in enumerate(fixture_cells):
                        check_contact("fixture_collision",index,swept,fixture,f"Rotating fixture {j} may contact stationary tool.")
            bc = next_bc
            query_points = world_points(points, bc, index_spec)
        run_move(index, "initial" if kind == "index" else kind, a, b, tool_id)
        elapsed += seconds
        emit(index, b, tool_id, a, kind)
    tol = plan["tolerance_mm"]
    # Signed-distance tolerance: no remaining material outside target dilated by
    # tolerance, and no missing material inside target eroded by tolerance.
    checks = [
        (
            "excess_material",
            lower & (target_d < -tol - rho),
            upper & (target_d < -tol + rho),
            "Final stock has excess material beyond target tolerance.",
        ),
        (
            "missing_material",
            ~upper & (target_d > tol + rho),
            ~lower & (target_d > tol - rho),
            "Final stock is missing required target material (including undersized initial stock).",
        ),
    ]
    for code, definite, possible, description in checks:
        if np.any(definite):
            issue(code, "definite", [], description)
        elif np.any(possible):
            issue(code, "uncertain", [], description + " Resolution cannot establish a pass.")
    result["passed"] = not issues
    result["validity"] = "valid" if result["passed"] else "invalid"
    result["verification"] = (
        "verified" if not issues else "violation"
        if any(i["certainty"] == "definite" for i in issues) else "unresolved"
    )
    removed_lo = initial_lower & ~upper
    removed_hi = initial_upper & ~lower
    result["stock_metrics"] = dict(
        initial_nominal_volume_mm3=float(initial_nominal.sum() * pitch**3),
        final_nominal_volume_mm3=float(nominal.sum() * pitch**3),
        removed_nominal_volume_mm3=float((initial_nominal & ~nominal).sum() * pitch**3),
        removed_volume_bounds_mm3=[
            float(removed_lo.sum() * pitch**3),
            float(removed_hi.sum() * pitch**3),
        ],
        final_volume_bounds_mm3=[float(lower.sum() * pitch**3), float(upper.sum() * pitch**3)],
    )
    if output:
        for name, mask in [
            ("final_stock", nominal),
            ("final_stock_lower", lower),
            ("final_stock_upper", upper),
        ]:
            voxel_mesh(mask, shape, origin, pitch).export(output / f"{name}.ply")
        (output / "trajectory.json").write_text(json.dumps(poses, indent=2) + "\n")
        result["artifacts"] = dict(
            final_stock="final_stock.ply",
            lower_stock="final_stock_lower.ply",
            upper_stock="final_stock_upper.ply",
            states=snapshots,
            trajectory="trajectory.json",
        )
        (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result
