# Compiled proximity backend experiment

Initial isolated experiment completed; runtime integration and validation are recorded below.

Official [libigl Python API](https://libigl.github.io/libigl-python-bindings/api/igl/) exposes `AABB.init` and `AABB.squared_distance`, returning squared distances, nearest triangle indices and closest points. The [libigl tutorial](https://libigl.github.io/tutorial/) recommends retaining the AABB when the mesh stays fixed across changing point batches.

The isolated script `scripts/demo/benchmark_geometry_backend.py` uses libigl2.6.3 through `uv run --no-project --python .venv/bin/python --with libigl`. It caps OMP/OpenBLAS threads to1 and runs at reduced scheduling priority. The project environment and lockfile are not modified.

It validates retained artifact hashes, compares deterministic centroid/vertex queries on both directions, checks nearest points lie on the reported triangles, and runs the unchanged bidirectional adaptive whole-triangle comparison with only a process-local `_closest` replacement. Triangle subdivision, planar-patch bounds, tolerance, tessellation margin, resource limits and failure classification stay unchanged.

Initial UMC02 query discrepancy: maximum1.59e-6mm between existing trimesh proximity and libigl. Exhaustive `closest_point_naive` on the10 worst queries matched libigl exactly; existing trimesh proximity retained the discrepancy. This is recorded as a baseline numerical difference, not hidden by widening the manufacturing tolerance.

Full results are written incrementally to `output/evaluation/geometry-backend-results.json`. Different nearest-face indices can be valid ties; returned point membership and distance agreement matter. Full pass/fail/unknown agreement and elapsed time must be checked before integrating anything.

## First complete case

UMC02: existing backend **66.141 s**, compiled libigl **14.119 s** (**4.68× faster**), both passed. The two directional accepted upper bounds were identical; a nearest-face tie changed a small amount of subdivision work. The comparison used the same saved STL target for both variants; original historical verification tessellated STEP in memory, so these timings are a fresh paired backend experiment, not a claim about identical historical runtime.

Synthetic boundary checks at0.127mm tolerance: translated box0mm and0.126mm pass with both backends;0.129mm and1mm fail with both. Exhausting triangle budget still yields unknown. These are useful boundary regressions, not comprehensive geometry certification.

UMC03 query discrepancies reached4.68e-6mm; exhaustive checks on the10 worst queries agreed with libigl within1.72e-15mm, while the old proximity method retained the larger discrepancy. No tolerance changes were made.

## Completed paired results

| Retained case | Trimesh | libigl | Speedup | Both verdicts |
|---|---:|---:|---:|---|
| UMC02 |66.141s|14.119s|4.68×|passed|
| UMC03 |70.626s|15.600s|4.53×|passed|
| B known failed stock |0.653s|0.062s|10.47×|failed|

The known failed stock remains failed in both directions with unchanged gouge classification. Worst nearest-query discrepancies are at most7.70e-6mm; exhaustive triangle search on the10 worst points in each affected direction agrees with libigl within8.52e-10mm. Returned points lie on their reported faces within1.49e-9mm. Face indices match around80% because shared vertices/edges admit ties; indices themselves need not match when the closest point remains valid.

Recommendation: integrate a cached immutable-mesh AABB into `_closest`, with finite/nonnegative distance and valid face-index checks, retaining the existing algorithm and resource rules. Cache lifetime must follow mesh identity/content; never reuse a tree after vertex/face mutation. Pin libigl2.6.3 and run existing whole-surface regression tests plus these retained cases in the actual project environment before enabling the backend. The experiment demonstrates approximately51–55seconds saved per retained passed comparison, not a guarantee for every mesh or total end-to-end runtime. Single paired runs, not statistically repeated performance measurements.

The initial isolated experiment changed no runtime code, project dependencies, learning files or Fusion state. The subsequently authorized integration is described below.

## Runtime integration

The proven backend is now integrated and pinned as `libigl==2.6.3`. Each directed surface comparison builds one AABB over immutable copies of its reference vertices/faces. Its lifetime ends with that directional check; no global cache or verdict reuse exists. Queries reject nonfinite inputs and malformed, nonfinite, negative-distance or invalid-index outputs. The full triangle bounds, tolerance, failure classification and resource-limit behavior remain unchanged. Comparison identity is now `bidirectional-adaptive-mesh-v2-libigl`.

All13 stock-comparison tests pass, including an exhaustive nearest-triangle oracle, immutable snapshot behavior, invalid native output rejection and tolerance boundary cases. The original performance table represents one paired run per case. Integration does not make those measurements statistically repeated or guarantee every live job will have the same duration.

Fresh checks in the integrated project environment: UMC02 passed in13.655s, UMC03 passed in13.787s, and known failed B stock remained failed in0.071s. Receipts: `output/evaluation/geometry-backend-integrated.json`. These runs reused exact retained meshes and did not control Fusion.

Live provenance: UMC08 began with the older outer fixed-verifier version, but loaded stock comparison lazily after integration. Its retained inner comparison method reports `bidirectional-adaptive-mesh-v2-libigl`; that identifies the backend actually used. The original receipt remains unchanged. Its first simulation reported 100% progress and zero issues, while the independent stock comparison still detected approximately 0.1905 mm of lower-flange gouging. This is additional live failure-detection evidence, not a paired speed benchmark.


## Exact STL degeneracy handling

UMC06's retained raw STL has eight facets with exactly repeated coordinates.
Removing only these zero-surface facets restores closed, consistently wound topology
without changing volume. Four other exactly collinear facets remain necessary for
edge incidence. The `v4-covered-collinear` comparison retains them in topology and
omits them from distance primitives/sampling only after an exact proof: rational
arithmetic on stored coordinates establishes collinearity, and the extreme endpoints
must form an edge of an adjacent positive-area triangle. That edge already contains
the entire omitted segment, so the represented surface is unchanged. No threshold,
approximate weld, hole fill or tolerance change is used. Uncovered lines and genuinely
open meshes still fail validation. BVH indices map back to original face indices.

Normalization receipts preserve the raw STL hash and enumerate removed repeated
facets and covered collinear facets. Historical unknown verdicts remain unchanged.
This handles an export representation defect; it does not itself establish a passed
stock comparison. Sixteen scoped tests pass, including covering-edge rejection,
nearest-point/index correctness and open-mesh controls.
