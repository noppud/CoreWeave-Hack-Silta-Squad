# UMC11: windowed octagonal cage

Ambitious project-authored challenge input, not a verified part. No CAD/CAM solution is supplied and no Fusion run was performed during preparation.

A stepped octagonal body has an open stepped circular cavity, eight through-wall upper windows and eight blind lower relief windows. The lower core remains solid: this avoids inventing an inaccessible deep interior under the existing short cutter. The eight facet access directions and two feature levels challenge toolpath planning while preserving connecting ribs and a rigid bottom flange.

## Analytical dimensions and access screen

- tool_diameter_mm: 12.700000
- flute_length_mm: 25.400000
- stickout_below_holder_mm: 33.020000
- top_cavity_depth_mm: 24.000000
- flute_margin_at_cavity_floor_mm: 1.400000
- holder_axial_standoff_at_cavity_floor_mm: 9.020000
- upper_through_window_normal_depth_mm: 14.000000
- breakthrough_margin_at_max_window_u_mm: 2.787594
- nominal_upper_wall_thickness_mm: 10.000000
- counterbore_rim_thickness_mm: 8.000000
- facet_width_mm: 30.651804
- window_edge_to_facet_corner_mm: 7.325902
- inner_cavity_circumferential_rib_arc_mm: 4.961877
- adjacent_window_nonintersection_u_margin_mm: 4.577728
- top_to_upper_window_mm: 5.000000
- upper_window_to_cavity_floor_mm: 3.000000
- window_levels_vertical_web_mm: 6.000000
- cavity_floor_to_lower_relief_top_mm: 3.000000
- lower_relief_to_collar_vertical_web_mm: 3.000000
- lower_relief_normal_depth_mm: 6.000000
- collar_height_mm: 6.000000
- collar_radial_step_mm: 2.000000
- max_diagonal_exterior_normal_removal_mm: 19.568542
- base_thickness_mm: 16.000000

The normal cuts intentionally meet only where the upper windows open into the top cavity. Adjacent upper windows retain positive circumferential ribs; lower reliefs remain separate. Each indexed pocket profile is reachable from its outward face with R8>=tool R6.35. Top cut 24 leaves 1.4 mm flute margin and 9.02 mm nominal holder standoff. These checks do not establish holder collision safety, cutting load or rib rigidity. Full target/CAM/stock verification remains necessary.

## Frozen input

- PDF SHA256: `bf9d10c72c4b9d0ccfff069bf7c988a889335082623a756e37e5fb6aa516d274`
- Config SHA256: `a0097da76c5a837035f0dd61fd25a4820455bcbf580ef5c8f5816f086a1512b5`
- Geometry SHA256: `664acd390f9c1604a7600e11675608ce8dc0d0f99ef76184b114c7ffbff09cf6`
- 12 drawing/machine/tool/fixture/check resource references checked.

Drawing: `output/pdf/demo-campaign/umc-11.pdf`. Config: `config/demo-campaign/umc-11-job.json`. Rebuild only this input: `uv run --with reportlab python scripts/demo/prepare_cage.py`. Machine/tool/fixture/setup placement/objective/check resources match the existing tall-pedestal job. Existing drawings, campaign queue, film and Fusion are untouched.

This is a shared-learning challenge: split=challenge and training_allowed=true. No run has been performed during preparation.

## Visual QA

Both A3 pages were rendered with Poppler at 1800 pixels and visually inspected. Top, typical facet and X-axis section are legible; all eight facet directions, cut extents, two feature levels and the analytical reach limitations are explicit. Twelve resource hashes and the geometry digest match. The actual T1 dimensions are read from the pinned existing job configuration during generation. This preparation did not operate Fusion or run the challenge.
