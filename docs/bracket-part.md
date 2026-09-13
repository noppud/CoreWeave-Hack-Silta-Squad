# UMC09: forked actuator bracket

Project-authored input only, not queued or run. No CAD/CAM solution is supplied.

The 80x80x70 AL6061 blank retains its bottom80x80x16 flange. A centered64x64 tower has a28mm-wide channel through both X ends,20mm deep, leaving two18mm ears. Two40x20 R10 blind obrounds enter opposite Y faces6mm, centered at X0,Z=-38.

Optional ear holes are omitted: DIA16 in an18mm ear would leave only1mm lateral wall; they add no necessary visual distinction or learning target.

## Analytical screen

- base_thickness_mm: 16 mm
- ear_width_mm: 18 mm
- channel_to_pocket_vertical_web_mm: 8 mm
- pocket_to_flange_vertical_web_mm: 6 mm
- pocket_end_to_tower_side_mm: 12 mm
- opposing_pocket_floor_web_mm: 52 mm
- top_depth_mm: 20 mm
- side_pocket_depth_mm: 6 mm
- exterior_normal_removal_mm: 8 mm

T1 diameter12.7mm fits channel28 and pocketheight20; R10 exceeds toolradius6.35. Top depth20, side depth6, and exterior normal removal8 are below25.4mm flute length. Tower height54 exceeds flute length, so it cannot be assumed machinable by one full-depth top contour. Actual indexed tool access, holder links and finished-stock conformity remain unverified.

## Frozen input

- PDF: `output/pdf/demo-campaign/umc-09.pdf` SHA256 `b182e794482976275a55eda14fbf906b7ce24f1fd247163b96b1c143255c3e50`
- Config: `config/demo-campaign/umc-09-job.json` SHA256 `3d392ab3ac83d66bc74b2c00bed9c52bdb21aae6aab59078a034fd8f245d10af`
- Geometry specification SHA256: `9d07bbcd02f89e27f4e00b11ef77943141c2d606066a7b5fa1ed397aec899cd4`

Machine, tools, fixture, placement, objective, baseline checks and cost assumptions are identical to `config/umc-actuator-tall-job.json`. Rebuild with `uv run --with reportlab python scripts/demo/prepare_bracket.py`. No edits to UMC02-08 or campaign queue.
