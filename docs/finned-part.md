# UMC10: finned instrument support

Project-authored benchmark drawing only. Held out as a fresh live-demo alternative; not queued or run. No CAD/CAM solution is included, and no internet part or thermal/manufacturing qualification is claimed.

The 80 x 80 x 70 AL6061 blank retains its 16 mm bottom flange. A centered 64 x 72 x 54 upper support has three 16 mm channels, open along the full X span and 18 mm deep. Four 6 mm fins remain. Two opposite Y-face obrounds are 40 x 20, R10, 6 mm deep and centered at X0, Z=-37.

## Analytical screen

- channel_width_mm: 16 mm
- fin_thickness_mm: 6 mm
- channel_depth_mm: 18 mm
- channel_to_pocket_vertical_web_mm: 9 mm
- pocket_to_flange_vertical_web_mm: 7 mm
- pocket_end_to_tower_side_mm: 12 mm
- opposing_pocket_floor_web_mm: 60 mm
- base_thickness_mm: 16 mm
- side_pocket_depth_mm: 6 mm
- exterior_normal_removal_x_mm: 8 mm
- exterior_normal_removal_y_mm: 4 mm

The seven alternating channel/fin intervals exactly fill the 72 mm width. Channel width 16 exceeds T1 diameter 12.7, pocket radius 10 exceeds tool radius 6.35, and all normal removal depths are below the 25.4 mm flute length. Channels and side pockets do not intersect. No inaccessible undercut or tiny internal planar corner is required. The 54 mm upper height still needs indexed access; fin stiffness, holder clearance and actual machining performance are not established by this drawing.

## Frozen resources

- PDF SHA256: `f8b170e1caeeeb6f65d58eb9864d5a1878aeb60ebb6b453c4eb1202b80f83865`
- Config SHA256: `704cfda34b9537685bb6a272e333c6349c4fabf464a3ee8702e5509f59549c17`
- Geometry specification SHA256: `972f48d92381b1391186ecb7fe80b06bf51e608f4594814cdc1909c7d5c4d01f`
- 12 drawing/machine/tool/fixture/check resource references verified against their SHA256.

Machine, tool library, fixture, placement, objective, costs and baseline checks remain identical to `config/umc-actuator-tall-job.json`. Training is disabled in the input spec to reserve freshness; this is not an assertion that every caller enforces the flag.

Rebuild this input only: `uv run --with reportlab python scripts/demo/prepare_finned.py`. Outputs: `output/pdf/demo-campaign/umc-10.pdf` and `config/demo-campaign/umc-10-job.json`. Existing parts, campaign queue, film and Fusion are untouched.

## Visual QA

The one-page A3 drawing was rendered to a 1800-pixel PNG and visually inspected. The three projections, coordinate intervals, pocket depths, tolerance notes and input-only label are legible. Twelve resource hashes and the canonical geometry hash were verified; UMC10 was absent from the active campaign when prepared.
