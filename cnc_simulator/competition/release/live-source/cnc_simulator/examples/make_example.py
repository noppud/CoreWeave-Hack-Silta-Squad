"""Regenerate the frozen test CAD. Requires the optional test dependencies."""

import json
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
stock = trimesh.creation.box([12, 10, 6])
stock.apply_translation([6, 5, 3])
ends = []
for x in [4, 8]:
    cylinder = trimesh.creation.cylinder(radius=2, height=5, sections=128)
    cylinder.apply_translation([x, 5, 5.5])  # bottom at Z=3, extends above stock
    ends.append(cylinder)
pocket = trimesh.convex.convex_hull(np.vstack([c.vertices for c in ends]))
target = trimesh.boolean.difference([stock, pocket], engine="manifold")
target.export(HERE / "pocket_target.stl")
tool = dict(
    diameter_mm=4,
    flute_length_mm=8,
    shaft_diameter_mm=4,
    shaft_length_mm=4,
    holder_diameter_mm=6,
    holder_length_mm=4,
)
plan = dict(
    units="mm",
    target=dict(type="mesh", path="pocket_target.stl"),
    stock=dict(type="box", min=[0, 0, 0], max=[12, 10, 6]),
    tools={"T1": tool, "T2": tool.copy()},
    fixtures=[],
    travel_limits=dict(min=[-20, -20, 0], max=[30, 30, 30]),
    initial_position=[2, 5, 8],
    initial_tool="T1",
    tolerance_mm=0.6,
    resolution_mm=0.2,
    rapid_mm_per_min=600,
    tool_change_seconds=4,
    moves=[
        dict(type="rapid", to=[4, 5, 8]),
        dict(type="tool_change", tool="T2"),
        dict(type="cut", to=[4, 5, 3], feed_mm_per_min=120),
        dict(type="cut", to=[8, 5, 3], feed_mm_per_min=120),
        dict(type="cut", to=[8, 5, 8], feed_mm_per_min=120),
        dict(type="dwell", seconds=1),
    ],
)
(HERE / "pocket.json").write_text(json.dumps(plan, indent=2) + "\n")
print(f"Target volume: {target.volume:.6f}; analytical: {720 - 3 * (16 + 4 * np.pi):.6f} mm^3")
