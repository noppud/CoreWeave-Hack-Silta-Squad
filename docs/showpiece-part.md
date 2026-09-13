# UMC08: octagonal instrument housing

Prepared, not run. This is a project-authored drawing benchmark, not a customer part or a verified manufacturing result. Feed config/demo-campaign/umc-08-job.json through the ordinary Astra PDF-to-CAD/CAM loop after UMC02-06. UMC07 remains held out and unchanged.

The finished body has a regular octagonal upper section, 74 mm across flats and 54 mm tall, on the original 80 x 80 x 16 mm square base. Eight blind vertical obrounds face eight azimuths separated by 45 degrees. The top has a concentric stepped cavity. The PDF contains a top view, elevation, mathematical isometric illustration, exact plane equations, all feature dimensions, material, tolerances and excluded features. No CAD, CAM, toolpaths or operation sequence is supplied.

The base input is config/umc-actuator-tall-job.json. Machine, assembled tools and limits, fixture artifact and placement, postprocessor, WCS, stock dimensions/position, cost assumptions and objective are copied unchanged. Drawing-specific stock preconditions explicitly permit the new upper exterior machining; the full lower base and bottom remain unchanged. Only T1 is enabled.

Analytical screening:

- Maximum original stock-to-diagonal-facet normal removal is 40*sqrt(2)-37 = 19.568542 mm; axis-aligned facets remove 3 mm. Facet faces extend to Z=-54, but their outward normals are horizontal.
- Slots are 16 mm wide, 30 mm high, R8, and 5 mm deep: larger than the 12.7 mm cutter and its 6.35 mm radius. Slot bottoms terminate at Z=-43, 11 mm above the flange.
- Top depths are 5 and 18 mm. The side feature bottoms remain at least 9 mm outside the outer cavity radius.
- The complete 80 x 80 x 16 mm lower base remains above the existing 60 x 60 mm support. No underside access is required.
- These dimensional checks do not establish holder clearance, reachable operation orientations, machining accuracy, or collision freedom. The unchanged actual Fusion verifier must decide those.

Artifacts:

- output/pdf/demo-campaign/umc-08.pdf: one-page A3 landscape drawing.
- config/demo-campaign/umc-08-job.json: pinned input and audit geometry, marked training.
- scripts/demo/prepare_showpiece.py: deterministic drawing/config generator. Its demo_part_spec metadata is for audit; read_inputs gives the planning agent the PDF and normal job inputs, not a CAD/CAM implementation.

Validation completed: PDF rendered and visually inspected; read_inputs(...).verify() passed all nested resource hashes; copied machine/tool/fixture/WCS/placement fields compared equal to the source configuration. No Fusion, model, simulator, or campaign execution was performed.

Reproduce with the bundled Python containing ReportLab:

    /Users/touko/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/demo/prepare_showpiece.py

Do not regenerate or edit the PDF/config while an active job references its hashes.
