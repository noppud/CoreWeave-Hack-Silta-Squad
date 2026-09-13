# Fusion background-control findings

Current authorization: Touko explicitly allowed foreground Fusion use for as long
as needed to finish and repeat-test the stock-export script. The implemented
route needs the unlocked shared desktop; background operation remains unproven.

## What is proven

- CAD/CAM and machine configuration are controlled through the Fusion add-in.
- Fixed machine-verification commands and the direct Issues reader have collected
  completed failing and zero-error simulations; no model is needed to read them.
- **Simulated-stock STL export now works unattended** through
  `python -m silta.cnc.stock_export`. The Python state machine uses a compiled
  Swift helper for native accessibility, guarded clicks and Apple Vision text
  recognition. It uses no agent/model calls.
- Four scripted exports produced identical triangle geometry: from the existing
  simulation, after rewinding to Start of Toolpath, and after launching a fresh
  machine simulation. The fresh simulation reported 100%, zero errors/warnings/
  process errors. This remains separate from whole-target acceptance.
- Each mesh has 1,158 triangles, a 152.4 × 50.8 × 25.4 mm bounding box and volume
  183,074.23 mm³. That agrees with Fusion's 183.074 cm³ displayed stock volume.
  Binary STL hashes vary with triangle ordering; compare triangle multisets.
- Evidence is local in `.private/fusion-live/stock-export-auto-01` through `04`
  and `stock-export-repeatability.json`. The earlier three-minute attempt below
  is a historical incomplete checkpoint, superseded by these successful tests.
- Whole-target comparison and automatic integration into the main fixed verifier
  are still outstanding. The exporter returns `verification_pass: false`.
- Fusion's AX window references are unreliable when backgrounded; foreground
  access exposes the save fields. The native helper fails if the Mac locks or
  another application owns the click target.

## Alternatives

| Route | Evidence and remaining test |
| --- | --- |
| Execute Fusion's actual stock command | Autodesk supports inspecting context-menu controls through `markingMenuDisplaying` and executing exposed command definitions. No Save Stock identifier appeared in our command inventory. Capture the actual menu/command once; the simulator may bypass this public event. A discovered command still needs an end-to-end export test, including its file dialog. |
| In-process AppKit events | Technically possible via a compatible PyObjC dependency inside Fusion, but not an Autodesk-supported simulation interface. Apple documents that mouse dispatch may activate a window. Direct canvas-responder delivery remains an untested compatibility experiment, not a promise of uninterrupted coding. No package installed. |
| Separate GUI session or computer | Apple supports a virtual display belonging to another authenticated account. This separates desktop interaction but requires Fusion/add-in/account setup and actual rendering validation. Another macOS Space alone does not provide independent keyboard/mouse control. |

## Earlier discovery probe (removed)

A temporary read-only listener was installed in the running Fusion process:
`.private/fusion-live/install-menu-command-probe.py`.
It observes `markingMenuDisplaying` and `commandStarting`, retains exposed command
definitions, and writes `.private/fusion-live/menu-command-probe-events.json`.
It does not change menu contents, execute a command, or request foreground focus.
The listener did not expose a Save Stock command identifier; menu traversal
encountered invalid controls. Both handlers were removed before the fresh
simulation test. The working export route uses observed on-screen labels and
native Save Stock fields. It does not depend on those probe handlers.

Do not substitute a pointwise Stock-to-Model probe or a matching volume for
whole-part comparison. One successful route does not establish background use.

Sources:
- [Autodesk menu event](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/UserInterface_markingMenuDisplaying.htm)
- [Autodesk CommandDefinition](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_CommandDefinition.htm)
- [Autodesk stock export instructions](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-save-the-stock-as-an-STL-from-simulation-in-Autodesk-HSM-and-Fusion-360.html)
- [Apple event architecture](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/EventOverview/EventArchitecture/EventArchitecture.html)
- [Apple Remote Desktop virtual display](https://support.apple.com/en-ph/guide/remote-desktop/apd4f46319e/mac)
- [PyObjC installation](https://pyobjc.readthedocs.io/en/latest/install.html)

## Foreground export test, September 12, 2026, approximately 17:50–17:53 PDT

The native canvas helper successfully opened the actual Stock submenu and
selected Save Stock. A Save Stock window appeared, initially displaying
"Receiving data...". Evidence: `.private/fusion-live/native-latest-region.png`.
No STL export was completed or verified during the offered foreground window.
The public listener recorded IronMachineSimulation and SimulationStockToModel,
but no Save Stock command identifier. Menu traversal raised an invalid-control
error; it needs per-control exception handling before another discovery test.

After the foreground interval, read-only Window Server inspection still listed
a Save Stock window. Targeted screenshots failed, Fusion reported AXFrontmost
false, and AX window references incorrectly resolved to application elements.
Foreground clicking stopped. Do not interpret this checkpoint as successful
export, background control, final stock comparison, or a complete verifier pass.
