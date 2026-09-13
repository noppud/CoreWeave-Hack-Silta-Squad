# Initial source-backed configuration

`soft-jaw-job.json` is **ready for CAM generation**. Machine assignment, stock dimensions, G54 and Part Position were applied and read back in Fusion. This is input readiness, not a completed simulation pass. Reject configurations before CAM execution when `unresolved` is nonempty. Paths are absolute for this checkout. Relocation must preserve the existing artifact hashes; never rehash changed bytes merely to make relocation pass.

The downloaded Autodesk Haas VF-2 model provides three-axis simulation geometry but generic settings include 99999 rpm, 100 tools and zero feed/rapid values. The proposed overrides use the [current official Haas specifications](https://www.haascnc.com/machines/vertical-mills/vf-series/models/small/vf-2.html): 8100 rpm, 16.5 m/min cutting feed, 25.4 m/min rapid, 20 tools, 4.20-second average tool change. These are published estimates, not measurements of a particular machine. Apply them to Fusion before comparing plans.

The job pins `haas-vf-2-linked.mch`, a byte copy of Fusion's persisted local machine definition after linking the saved VF-2 model in the Silta CNC Hackathon project. It retains 8100 rpm, 20 tools and approximately 4.2-second tool change. Actual setup assignment through `machineLibrary.machineAtURL` succeeded and the full machine is visible. The original download remains pinned as `source_definition`. CAM time estimates use the explicit feed/rapid assumptions above; controller-field unit verification and completed machining simulation remain separate.

`starter-tools-numbered.json` retains all six official cutter definitions. Only post numbers and offsets change to1–6. Raw inch geometry stays in inches. Tools1–2 are enabled: 6000rpm with feeds derived from the official wrought-aluminum slot presets, scaled with RPM and derated50%. Tools3–6 have zero/missing vendor presets and stay disabled because the initial slot task can use endmills. Do not mistake the derived simulation bounds for validated physical cutting advice. The active starter-tools-assembled.json was imported and re-exported by Fusion2705.1.15 with holder04-0010 segments, 96.52/90.17mm assembly gauges and the configured feeds preserved. Original catalog geometry/library remain pinned separately. Tool-assembly-report.json records the readback; operation assignment, cutting engagement and holder clearance still require CAM/simulation verification.

`haas-next-generation.cps` is downloaded official Autodesk post code, with URL and SHA256 pinned in the job. It has not yet been successfully used in live Fusion. This is an existing source asset, not authored project code. No physical-machine compatibility is claimed.

The Soft Jaw drawing specifies AL6061 and ±0.005inch. Preserve its obround features. We explicitly assume a pre-sized152.4×50.8×25.4mm blank, machining its internal features; outside preparation and final manual deburring are excluded. G54 is top center. The prepared vise archive includes two conservative Haas09-0108 parallel envelopes (152.4×12.7×38.1mm). Actual Fusion faces give 5.969mm jaw contact depth; the earlier6.35mm guess is superseded. The exported archive was reopened with all19 bodies and positions preserved. BRep tests found no stock/fixture overlap and clear through-slot envelopes including1mm breakthrough; the parallels rest on the two bed lands and span the center recess. These are geometric simulation inputs, not physical cutting-load certification. Part Position uses model box top center, offsets [0, -107.247656, 136.525]mm relative to the table attachment, derived from the actual vise base. These settings and a zero-origin identity G54 matrix read back in Fusion; full-machine collision verification remains pending. Tool1's25.4mm flute length makes breakthrough depth an actual check, not a detail to ignore.

`checks/baseline.py` consumes the actual `analysis` artifact and checks tool membership/geometry, generated toolpaths, explicit operation errors, positive finite cutting parameters under fixed machine/tool bounds, and presence of NC output. Missing measurement/configuration fails preflight. It does not assert collision-free motion, tolerance conformity, tool reach or realistic cutting physics. A pass must still enter Fusion simulation.


## Relocating a checkout

A fresh clone is not a runnable Fusion installation. Some pinned drawings, machine
archives and retained artifacts may not be distributed with the clone. Verify the
new checkout before writing a relocated configuration:

```sh
.venv/bin/python scripts/demo/relocate_config.py config/demo-campaign/umc-07-job.json \
  --old-root /Users/touko/work/helios-one/repos/coreweavehack \
  --new-root /absolute/new/checkout --verify-only
```

The command checks destination bytes against every existing `path`/`sha256` pin.
It rejects missing or changed pinned resources, ambiguous relative paths and
paths outside the declared source root. It does not download missing resources,
change hashes, rewrite account IDs, or contact Fusion. After successful verification,
replace `--verify-only` with `--output /absolute/new/checkout/config/relocated-job.json`.
The destination must not already exist. Active configuration files are not edited.
For an already relocated config, use the new checkout for both roots.

## Fusion prerequisites beyond local files

The retained configurations bind real account and library state. For example,
UMC jobs refer to `user://Silta UMC750 demo.mch`, a machine-model data-file/version
URN, and the `Silta CNC Hackathon` project ID. A copied `.mch` file does not establish
access to its linked cloud machine model. These IDs remain unchanged by relocation.

The destination machine needs a signed-in Fusion account with access to that exact
project and linked saved machine document, plus a Fusion entitlement that permits
the required indexed CAM and machine simulation workflow. Install and run the
SiltaBridge add-in; verify its local request/response transport before submitting a
job. Native verification also needs the repository's macOS Accessibility/screen
capture permissions and a usable Fusion foreground window. Python tests do not
establish any of those conditions.

Before CAM generation, verify the exact local machine-library URL resolves through
`CAMManager.get().libraryManager.machineLibrary.machineAtURL(URL.create(...))`,
and that the machine has its actual simulation model linked. Validate the selected
setup assignment, G54 frame, fixture/Part Position and tool assemblies against the
configuration; importing an archive alone does not establish these bindings. See
[the machine setup guide](../fusion/MACHINE-SETUP.md),
[fixture setup](../fusion/FIXTURE-SETUP.md),
[tool setup](../fusion/TOOL-SETUP.md) and
[indexed API notes](../fusion/INDEXED_CAM_API.md).

If the original account resources are unavailable, first provision and link the
machine in the destination account, then explicitly create a reviewed configuration
with the newly observed project/model/library references. Re-export changed linked
resource bytes and record their new provenance as a configuration change; that is
not path relocation. Exact candidate reopening additionally requires its pinned
saved-document version and project access, as enforced by `fusion/cam_documents.py`.

The local integration evidence is from Fusion 2705.1.15. API/post-engine compatibility,
actual machine visibility and a full saved-candidate simulation/stock verification
must be established on the destination installation. A relocation report only proves
local paths and pinned bytes, never demo readiness or a manufacturing verdict.
