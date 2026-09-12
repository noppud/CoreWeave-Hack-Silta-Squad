# Cutter and holder preparation

`prepare_tool_assemblies.py` selects the two enabled, hash-pinned Haas cutters,
attaches the pinned Haas 04-0010 holder segments, and retains one cutting preset
per tool. It writes a proposed library, then `apply` imports the versioned library
using `ToolLibrary.createFromJson`, retrieves each `Tool` with `item`, serializes
it, and checks the complete library's exported values again. It makes no Hub library, setup, or operation changes.

| Tool | Diameter | Exposed flutes | Below holder | Holder gauge | Assembly gauge | RPM | Cutting feed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 / 03-0086 | 12.7 mm | 25.4 mm | 33.02 mm | 63.5 mm | 96.52 mm | 6000 | 1371.6 mm/min |
| 2 / 03-0083 | 6.35 mm | 19.05 mm | 26.67 mm | 63.5 mm | 90.17 mm | 6000 | 685.8 mm/min |

These feeds are the configured simulation assumptions. Supplier plunge/ramp
proportions are retained under that feed ceiling. The prepared presets do not
prevent an operation from overriding feeds: operation readback/checks remain
necessary. Live Fusion 2705.1.15 omits `v_f_retract` from these milling presets;
the helper omits it from the proposed preset and explicitly defers retract feed,
rapid behavior and clearance to operation readback and simulation. It preserves
and verifies operative cutting/lead/plunge/ramp/transition feeds, RPM and `f_z`.
Fusion also serialized `f_n` equal to `f_z` in this live case; the helper leaves
`f_n` generation to Fusion and records the actual value. The generic installed
ToolPreset documentation does not specify this field's per-tool semantics. Exposed flute length is not a blanket allowed Z depth; actual engaged
cut length, holder clearance and breakthrough must be checked in the CAM setup
and simulation. Collet bore labels in the job do not add separate collet geometry;
the pinned chuck's vendor exterior segments are the collision envelope.

Through the running Silta bridge, load this module and call:

```python
result = namespace['apply'](app, {
    'config_path': '/Users/touko/work/helios-one/repos/coreweavehack/config/soft-jaw-job.json',
    'output_directory': '/Users/touko/work/helios-one/repos/coreweavehack/.private/fusion-live/tools-v1',
})
```

Use a fresh output directory. `tools-assembled-input.json` is only a proposal.
Actual Fusion serialization is preserved even if comparison fails. Only a complete
`tool-assembly-report.json` with `fusion_tool_library_roundtrip_passed_not_assigned`
proves the import/export values survived; it does **not** prove assignment,
machine simulation, real cutting safety, or job readiness. The parent must review
the result before pinning the exported library in job inputs.

API authority: installed Fusion 2705.1.15 `adsk/defs/adsk/cam.py`, `Tool` and
`ToolLibrary`: `createFromJson`, `item`, `count`, `toJson`. The helper retains
the vendor JSON's version 36 because Autodesk warns import migrations may change
values. JSON field authority is the pinned Haas cutter/holder export; the nested
holder and assembly-gauge relationship also appear in Autodesk's published
[import/export reproduction and engineering reply](https://forums.autodesk.com/t5/fusion-api-and-scripts-forum/bug-with-use-stepdown-and-use-stepover-in-adsk-cam-toollibrary/td-p/13371616).
Readback, rather than that example, is the acceptance evidence for this installation.

Live `tools-v1` revealed that passing a library envelope to `Tool.createFromJson`
produces an unspecified zero-dimension tool rather than an exception. The helper
rejected that readback. The corrected importer passes the envelope only to
`ToolLibrary.createFromJson`; its next live run is still required.
