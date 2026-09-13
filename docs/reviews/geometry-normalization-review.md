# Independent geometry-normalization review

Reviewed the `bidirectional-adaptive-mesh-v4-covered-collinear` implementation and its `fusion-fixed-ui-stock-v5-exact-collinear` integration. No Fusion operation or runtime implementation change was performed during this review.

The new rules do not substitute zero-area facets for positive-area surface geometry:

- Raw facets with exactly repeated vertex coordinates are removed before the existing mesh processing. Their indices/count and original export hash remain recorded; the raw file is unchanged.
- Other zero-area facets stay in the topological mesh. Exact rational arithmetic on stored coordinates must prove collinearity. The two extreme vertices must also form an edge of a positive-area triangle. That positive triangle already contains the entire segment, so omitting the zero-area facet from distance primitives and sampling leaves the represented geometric surface unchanged.
- Watertightness, winding, positive volume and the bidirectional distance/tolerance gates remain required. Uncovered zero-area segments and numerically underflowed but noncollinear triangles are rejected.

Added15 independent regression controls in `tests/test_stock_topology_review.py`: one closed box with a split edge and a covered collinear joining facet passes; removing each of its13 positive-area triangles is rejected even when the exported mesh also includes repeated-coordinate and collinear facets; a truly noncollinear triangle whose floating-point area underflows to zero is rejected by the exact test. Raw export bytes remain unchanged in the file-based tests. All31 tests across this review file and the existing stock-comparison file pass.

One important limit remains: `load_stock_mesh` still calls the pre-existing `Trimesh.process()` path. The installed implementation merges vertices by rounded coordinate precision and removes nonfinite values before downstream validation. Those behaviors also existed in the previous `process=True` loader. Therefore “exact” describes the newly added facet-removal/coverage rules, not a claim that the whole preprocessing pipeline performs only exact raw-coordinate operations. These controls establish behavior on the tested open surfaces; they are not a general raw-mesh certification or physical manufacturing validation.

The original UMC06 unknown result must remain unchanged. The reported63.9-second offline comparison of retained stock is separate from a fresh live recovery. This source/test review does not establish that the live recovery passed; that requires its own completed bound verdict.

Latest live read-only checkpoint: UMC06 recovery1 ended incomplete at2026-09-13T07:06:03Z after a Fusion bridge request timeout, with no verified best recorded. This does not convert the original unknown verdict into a pass or invalidate the separate offline geometry measurement. Further live recovery is owned by the main task.
