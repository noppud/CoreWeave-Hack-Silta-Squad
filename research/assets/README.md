# Public Fusion starter assets

Downloaded 2026-09-12 from Autodesk's public training and machine/tool libraries. These are training inputs and reference artifacts, not our generated results. No Fusion import or live animation has been tested yet. Preserve source attribution; no redistribution license was established.

## Recommended machine and visualization

Use **HAAS VF-2 without a rotary table**. `haas-vf-2.mch` is the official definition; **`haas-vf-2.f3d` is the actual 2 MB simulation geometry**, downloaded from the model URL inside that definition. The live library marks it simulation-ready with X/Y table motion and Z head motion. The official `haas-vf2-machine-simulation-guide.pdf` explicitly demonstrates downloading this model, positioning a vise, then playing **Simulate with Machine**. This supports an animated machine/table, not merely a floating cutter. Toolchanger animation itself has not been verified.

Sources: [machine library](https://cam.autodesk.com/machineslist), [machine entry data](https://cam.autodesk.com/machines/machines/machines.json), [official animation guide](https://files.upskill-dev.autodesk.com/public/aex/HaasF360/C4-Machined_Part_Finish_Inspect/pdf/221215_SbS_S4-M3-02_Machine-simulation.pdf), [Haas VF-2 specifications](https://www.haascnc.com/machines/vertical-mills/vf-series/models/small/vf-2.html).

Important calibration gap: Autodesk's generic entry uses 100 tools and a 15-second change; the current Haas product page describes a 20-tool VF-2. Do not silently equate generic simulator defaults with a calibrated physical machine. Establish and freeze the exact simulated configuration before comparing times.

## Selected inputs

Files in `selected/` are byte-for-byte copies from original archives except the explicitly named tool subsets.

| Input | Role | Reference |
|---|---|---|
| `soft-jaw-drawing.pdf` | First drawing-to-CAD smoke test: simple AL6061 rectangular jaw with counterbored holes. Dimensioned, 1 page; visually checked. | Source archive includes Soft Jaw.f3d, but its exact match to this challenge has not been established. |
| `engine-case-drawing.pdf` | Richer pocket/bore/drilling test, AL6061; dimensioned, 1 page; visually checked. Requires multiple setups for all features. | `engine-case-reference.f3d`, `engine-case-ready-to-program.f3d`; archive also contains programmed F3Z and setup sheets. Compare geometry before treating them as ground truth. |
| `caliper-drawing-rev-b.pdf` | More visually compelling advanced part; 5 pages including front/back/piston drawings, visually checked. Use one specified component rather than treating an assembly as a single part. | `caliper-reference.f3d` comes in same official challenge dataset. |
| `../simple-3x-part-cam-challenge.f3d` | Separate 3-axis CAM strategy exercise with a supplied CAD target. | Official 2.5/3-axis challenge. No dimensioned PDF found for this particular shape. |

Do not expose programmed CAM/reference geometry to the drawing-to-CAD agent when evaluating reconstruction. Multiple setups are not extra machine axes. The complete engine/caliper parts may require threading and tools beyond the initial starter library; do not claim all are executable with six tools before CAM verification.

[Intro CAD/CAM course and download](https://www.autodesk.com/learn/ondemand/course/fusion360-intro-cad-cam-practical-cnc-associate), [Haas course and challenge download](https://www.autodesk.com/learn/ondemand/course/haas-fusion-360-blueprints-cad-cam-cnc), [3-axis challenge](https://www.autodesk.com/learn/ondemand/course/cam-2-5-and-3-axis-milling/module/62lzTb4Lrop0yTnln9plw2).

## Tools and workholding

Full official vendor libraries: `haas-tooling.json`, `haas-holders.json`. Starter subset keeps original entries unchanged:

- 03-0086: 1/2-inch, 3-flute carbide flat end mill.
- 03-0083: 1/4-inch, 3-flute carbide flat end mill.
- 03-0590: 1/4-inch, 2-flute carbide ball end mill.
- 03-2901: 1/4-inch carbide drill, 140-degree point.
- 03-2222: 1/4-inch carbide spot drill, 142-degree point.
- 03-0612: 1/4-inch carbide 45-degree chamfer mill.
- Holder candidate 04-0010: CT40 ER32, 2.5-inch gauge length. Proper collets, assembled stickout and holder assignment still need defining; subset is not a ready-to-cut assembly library.

`selected/starter-tools-unmodified.json` and `selected/starter-holder-unmodified.json` contain these exact records. Use individual material-appropriate presets after checking against the machine spindle limit. Tool numbers in original entries may be zero; assign unique numbers during setup. Source: [Autodesk vendor library](https://cam.autodesk.com/hsmtools), [Haas tooling integration instructions](https://www.autodesk.com/products/fusion-360/blog/haas-tooling-fusion-360-tool-library).

Two fixture candidates are downloaded: official course `haas-vise-05-0404.f3d` and `generic-vise.f3d`. Load one and establish stock clamping/location before treating collision checks as meaningful.

`download-sources.json` maps download names to exact URLs; `file-manifest.json` records hashes and sizes. `previews/` contains read-only PDF render checks.
