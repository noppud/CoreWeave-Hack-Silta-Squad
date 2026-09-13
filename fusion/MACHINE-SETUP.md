# Apply selected machine settings

`apply_machine_profile.py` prepares a separate machine file from the SHA-pinned
source. It retains simulation-model references and all fixture/axis transforms.
It changes the selected spindle RPM, tool capacity, feed override ratio and
tool-change estimate, then imports and exports through Fusion and verifies the
roundtrip. An explicit `setup_index` additionally assigns it to that setup.

After the bridge responds, send this source through `run_script` (replace paths
with the checkout and a fresh job artifact directory):

```python
import runpy
helper = runpy.run_path('/absolute/checkout/fusion/apply_machine_profile.py')
result = helper['apply'](app, {
    'config_path': '/absolute/checkout/config/soft-jaw-job.json',
    'output_directory': '/absolute/job/machine-attempt-1',
    # 'setup_index': 0,  # Include only when that exact setup should change.
})
```

The installed API supports `Machine.create(MachineFromFileInput.create(path))`.
It exposes `Machine.save(location,path)` but labels save **not officially
supported**. The helper validates its output rather than assuming it works.
It does not claim the simulation model loaded unless `has_simulation_model`
returns true, and never claims verification success.

Live integration on Fusion 2705.1.15 successfully imported and exported the
configured VF-2 definition. An unattached `Machine` reports `isValid=False` in
this build even while its identity, simulation-model property and export work.
The helper records that flag and requires serialized readback of the configured
values. Setup assignment and completed simulation remain separate checks.

The source's controller speed fields have no explicit speed-unit declaration.
No supported corresponding setters were found in the installed API. These are
intentionally preserved; inspect/configure them in Fusion's machine editor.
Explicit maximum cutting feed remains enforced by cheap checks; rapid speed and
tool-change time are inputs to `CAM.getMachiningTime`. The report retains this
remaining limitation. No fixture position or tool assembly is inferred, and the
job configuration is never automatically marked ready.
