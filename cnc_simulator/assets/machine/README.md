# Downloaded Haas reference assets

The local viewer's **Haas VF-2** and **Setup** buttons use native tessellated
geometry from the existing project's downloaded Haas VF-2 and prepared vise:
11 machine bodies, 19 fixture/parallels bodies, and the retained soft-jaw CAD.
The target measures 152.4 × 50.8 × 25.4 mm. Both tool envelopes come from
`config/starter-tools-assembled.json`, including holder segment profiles.

`export-receipt.json` records the one-time export. `machine-raw.json`,
`fixture-raw.json`, and `target-raw.json` hold the triangles in millimetres.
`../../scripts/export_fusion_assets.py` runs inside the existing Fusion bridge
with `app`, `adsk`, and `payload` injected; payload supplies an absolute output
directory. It reads already-open documents and does not activate or save them.
The mesh visualization tolerance is 0.2 mm. The target export comes from the
retained CAM document, not from a newly validated STEP import.

Run `python cnc_simulator/scripts/build_machine_assets.py` from the repository
to package the exports into `viewer/dist/assets/haas-vf2.json`. The builder checks
source hashes against the pinned job configuration. No Fusion dependency is
needed to serve these assets or run the programmatic simulator.

The reference pose uses saved G54 placement and the downloaded axis directions,
travel ranges and spindle gauge plane. Selecting T1 or T2 adjusts the head for
its gauge length while retaining 50 mm tool-tip clearance above G54. The fixture
base is on the machine table. Setup hides the enclosure for a closer look.

This is a parked reference visual. The pocket example has its own tools and
fixtures; its verdict does not cover these machine/reference assets. Full machine
collision checking, this soft-jaw machining job, and controller motion are not
implemented by this asset conversion.

Validation: four asset tests check pinned hashes, complete mesh inventory,
finite/index-valid triangles, target scale, fixture table contact, tool dimensions
and parked travel. Browser checks cover the machine and setup views and T2
selection. These checks do not certify manufacturing safety.
