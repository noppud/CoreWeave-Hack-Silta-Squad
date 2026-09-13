# Six additional indexed Fusion targets

Prepared inputs only: these files contain no CAD result, CAM recipe, simulation verdict or claimed completion. The main Astra flow must derive each unique CAD target from its PDF and generate/verify machining normally.

Five training targets extend the four existing learning parts plus the actuator example to ten completed jobs **once all five actually complete**. The sixth is the eleventh, held-out assessment target. The manifest records this split; the runner must enforce it. Do not train, rewrite prompts or promote checks using the held-out result.

| Job | Target | Split | Distinguishing dimensions |
|---|---|---|---|
| `umc-02` | Compact sensor node | Training | Top recess diameters42/32, depths5/16; side44x40, depth6, island10 |
| `umc-03` | Drive encoder housing | Training | Top48/36, depths4/18; side50x40, depth7 |
| `umc-04` | Valve feedback block | Training | Top46/38, depths6/20; side46x42, depth6 |
| `umc-05` | Wide service manifold | Training | Top54/42, depths4/16; side52x40, depth8 |
| `umc-06` | Offset monitoring block | Training | Top center(-3,2); differing X/Y side dimensions and horizontal offsets |
| `umc-07` | Cross-port service block | Held out | Top center(2,-2),50/40 depths5/19; different side sizes, offsets and depths |

Each drawing specifies all hole positions/depths, pocket centers and depths, R8 side corners, concentric side islands, AL6061, and general tolerance+/-0.127mm. All targets require top and four indexed side faces (3+2). No simultaneous five-axis contour is specified.

The unchanged base setup is `config/umc-actuator-tall-job.json`: 80x80x70 pre-sized blank, G54 top center, stock bottomZ=-70, one T1 diameter12.7 flat end mill, 25.4mm flute, existing UMC-750 linked machine and tall pedestal. The pinned pedestal remains:

`config/umc-tall-pedestal-g54.f3d` — SHA256 `b64840531f39ffca6a49e715dc478ff56284c7f8b99ae6c97ace8b62cd7a3679`.

Bottom and exterior remain as supplied, except the explicitly defined blind openings. Mounting from below is a fixture precondition, not additional bottom geometry. All corner radii exceed cutter radius, all island passages exceed cutter diameter, top depths are at most20mm, side depths at most8mm, and the lowest side pocket remains at or aboveZ=-54. Generator assertions check these dimensional constraints and separation of top/side cuts. They do not replace fixture/holder/machine simulation.

## Files and reproducibility

- PDFs: `output/pdf/demo-campaign/umc-02.pdf` through `umc-07.pdf`.
- Jobs: `config/demo-campaign/umc-02-job.json` through `umc-07-job.json`.
- Index: `config/demo-campaign/manifest.json` provides paths, PDF hashes, unique geometry-spec hashes, split and `prepared_not_run` status.
- Source: `scripts/demo/prepare_fusion_campaign.py`, using ReportLab with deterministic PDF metadata.

Run the generator with Python containing ReportLab. It recreates the six PDFs/configs from the current base config; do not regenerate once a campaign has pinned these inputs. Any revised drawing/setup requires a new input version and rerun.

The extra `demo_part_spec` object is a canonical dimensional target description for audit, not a precomputed CAD model or machining plan. `geometry_sha256` hashes this target specification, not nonexistent CAD bytes. The standard `drawings` entries pin the actual PDF bytes. `read_inputs(...).verify()` succeeds for all six configurations and their nested resources.

All six final one-page PDFs were rendered with Poppler and visually inspected for readable dimensions and unclipped schedules. The designs are explicitly labeled project-authored simulation benchmarks; none is represented as customer work or an internet-sourced drawing. Their feature family follows the existing `output/pdf/umc-actuator-housing.pdf`; machine/tool/fixture provenance is preserved from the base configuration.
