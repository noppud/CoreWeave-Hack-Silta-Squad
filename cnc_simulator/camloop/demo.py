"""Small accepted geometry jobs and frozen simulator-labelled evaluation cases."""

import copy
import json
from pathlib import Path

import numpy as np
import trimesh
from cncsim import simulate

from .common import digest, file_hash, freeze_job, load_job, save

ROOT = Path(__file__).resolve().parents[1]


def verifier_digest():
    from cncsim import geometry, simulator

    return digest([file_hash(simulator.__file__), file_hash(geometry.__file__)])


def prepare_jobs(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    jobs = []
    for name, width, floor in [("part-a", 12, 3), ("part-b", 14, 2.8), ("part-c", 12, 3.4)]:
        directory = root / name
        directory.mkdir(exist_ok=True)
        plan = json.loads((ROOT / "examples/pocket.json").read_text())
        plan["stock"]["max"][0] = width
        plan["target"]["path"] = "target.stl"
        plan["tools"] = {"T1": plan["tools"]["T1"]}
        # Deliberately overdeep starting candidate. It is not an agent result.
        plan["moves"] = [
            dict(type="rapid", to=[4, 5, 8]),
            dict(type="cut", to=[4, 5, floor - 1.6], feed_mm_per_min=120),
            dict(type="cut", to=[width - 4, 5, floor - 1.6], feed_mm_per_min=120),
            dict(type="cut", to=[width - 4, 5, 8], feed_mm_per_min=120),
            dict(type="dwell", seconds=1),
            dict(type="rapid", to=[2, 5, 8]),
        ]
        stock = trimesh.creation.box([width, 10, 6])
        stock.apply_translation([width / 2, 5, 3])
        ends = []
        for x in (4, width - 4):
            mesh = trimesh.creation.cylinder(radius=2, height=8 - floor, sections=128)
            mesh.apply_translation([x, 5, (8 + floor) / 2])
            ends.append(mesh)
        pocket = trimesh.convex.convex_hull(np.vstack([m.vertices for m in ends]))
        trimesh.boolean.difference([stock, pocket], engine="manifold").export(
            directory / "target.stl"
        )
        save(directory / "plan.json", plan)
        save(
            directory / "job.json",
            dict(
                id=name,
                plan="plan.json",
                family="capsule_pocket",
                feature=dict(
                    centerline_start=[4, 5],
                    centerline_end=[width - 4, 5],
                    radius=2,
                    floor_z=floor,
                    stock_top_z=6,
                ),
                feed_limits_mm_min={"T1": 240},
                max_moves=100,
                final_position=[2, 5, 8],
            ),
        )
        jobs.append(directory / "job.json")
    return jobs


def reference_moves(job, *, feed=120):
    feature = job["feature"]
    a, b, z = feature["centerline_start"], feature["centerline_end"], feature["floor_z"]
    return [
        dict(type="rapid", to=[*a, 8]),
        dict(type="cut", to=[*a, z], feed_mm_per_min=feed),
        dict(type="cut", to=[*b, z], feed_mm_per_min=feed),
        dict(type="cut", to=[*b, 8], feed_mm_per_min=feed),
        *([dict(type="rapid", to=job["final_position"])] if "final_position" in job else []),
    ]


def build_corpus(workspace):
    workspace = Path(workspace).resolve()
    jobs = prepare_jobs(workspace / "jobs")
    root = workspace / "corpus"
    if root.exists():
        raise ValueError("Corpus already exists; use a new workspace to rebuild frozen labels")
    root.mkdir()
    cases = []
    # B is reserved for the next-part demonstration, not used by either gate.
    for source in [jobs[0], jobs[2]]:
        job, fingerprint = freeze_job(load_job(source), root / source.parent.name)
        for kind in ["valid", "overdeep", "missed", "valid-air-cut"]:
            plan = copy.deepcopy(job["plan"])
            if kind == "valid":
                plan["moves"] = reference_moves(job)
            elif kind == "valid-air-cut":
                plan["moves"] = [
                    dict(type="rapid", to=[20, 5, 8]),
                    dict(type="cut", to=[20, 5, 1], feed_mm_per_min=120),
                    dict(type="cut", to=[20, 5, 8], feed_mm_per_min=120),
                    dict(type="rapid", to=plan["initial_position"]),
                ] + reference_moves(job)
            elif kind == "missed":
                plan["moves"] = [dict(type="rapid", to=[4, 5, 8])]
            result = simulate(plan)
            expected = "valid" if kind.startswith("valid") else "invalid"
            if result["validity"] != expected:
                raise RuntimeError(
                    f"Corpus {job['id']}/{kind}: expected {expected}, got {result['validity']}"
                )
            case = dict(
                id=f"{job['id']}-{kind}",
                job=job,
                fingerprint=fingerprint,
                plan=plan,
                plan_hash=digest(plan),
                result=result,
                verifier=verifier_digest(),
            )
            path = root / f"{job['id']}-{kind}.json"
            save(path, case)
            cases.append(dict(path=str(path), sha256=file_hash(path)))
            print(f"Labelled {case['id']}: {result['validity']}", flush=True)
    save(root / "index.json", dict(cases=cases, held_out="part-b", verifier=verifier_digest()))
    return root / "index.json"
