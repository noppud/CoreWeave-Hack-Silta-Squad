# Installed Fusion indexed CAM API notes

These are integration findings from Fusion 2705.1.15, not machining recommendations
or learned policy. The controller supplies the setup, fixed target and approved tools.
Choose machining geometry and cutting parameters from the current drawing and inputs.

CAD setup uses millimetre display units, with centimetres for raw API geometry.
`defaultLengthUnits` is read-only. `distanceDisplayUnits` is the writable design
property. Sketches on a face can contain fixed projected curves; do not blindly
set `isFixed=True` on every curve. Leave existing fixed/projected entities alone.

`ConstructionPlane.isVisible` is read-only; use `isLightBulbOn` to change a
construction plane's browser visibility. Cosmetic display cleanup is optional:
do not let a guessed visibility setter invalidate an otherwise complete solid.
The installed `ConstructionPlane` definition exposes `_set_isLightBulbOn` and
only `_get_isVisible` (observed during the UMC-03 CAD attempt).

For a side pocket, the following reference form generated toolpaths successfully:

```python
op = setup.operations.createInput('pocket2d')
op.tool = tools[1]
op.parameters.itemByName('overrideToolView').expression = 'true'
op.parameters.itemByName('view_orientation_mode').expression = "'axesZX'"
op.parameters.itemByName('view_orientation_axisZ').value.value = [pocket_floor_face]
op.parameters.itemByName('view_orientation_axisX').value.value = [root.zConstructionAxis]
op.parameters.itemByName('view_origin_mode').expression = "'jobOrigin'"
```

Select the actual planar pocket floor whose outward normal is the desired tool
axis, and a perpendicular axis for X. Assigning a BRepFace to the surface-point
field used by `surfaceNormalX` left an unresolved reference. Recreate such an
operation with fresh references instead of retaining that invalid selection.

Pocket face selections preserve islands:

```python
value = op.parameters.itemByName('pockets').value
curves = value.getCurveSelections()
selection = curves.createNewPocketSelection()
selection.inputGeometry = [pocket_floor_face]
selection.isSelectingSamePlaneFaces = False
value.applyCurveSelections(curves)
```

For an annular counterbore floor, a pocket selection may clear only the annulus.
To clear its complete outer disk first, select the outer loop's edges as a closed
chain and verify the cutting side. The tested circular outer chain needed
`chain.isReverted = True`; the opposite direction cut outside the boundary.
Inspect the resulting toolpath and simulation for the actual geometry.

Narrow holes require lead/ramp geometry that fits the remaining cutter clearance.
The API exposes `doLeadIn`, `doLeadOut`, `leadInVerticalRadius`,
`leadOutVerticalRadius`, `helicalRampDiameter`, `minimumRampDiameter` and
`minimumCuttingRadius`. Use the live catalogue for available parameters and values.
This note does not prescribe dimensions, feeds, depths or strategy.

Parameter names are strategy-specific. The installed catalogue reports
`pocket_clearing` as **3D Offset Roughing (Pocket)** and `adaptive` as
**3D Adaptive Roughing**, both generation-allowed. The controller now requests
their full parameter descriptions alongside the five existing 2D/drilling examples.
Read the parameter list under the selected strategy: names shown for `pocket2d`
must not be copied into `pocket_clearing` without checking. In the retained UMC11
attempt, `pocket_clearing/feedHeight_mode` and `pocket_clearing/doLeadIn` were missing.
This catalogue coverage is API integration support, not a recommendation to choose
3D strategies or any cutting policy. Unsupported strategies still retain their
catalogue error; no parameter defaults or verification conditions are bypassed.

Compatibility evidence: `runs/demo-umc-umc-11/workspace/cam-0001/cam-api-catalog.json`.
That historical file lists these 3D strategies but contains detailed parameters
only for the original five examples. It remains unchanged; future runs collect
the additional descriptions directly from Fusion.

Evidence: `runs/umc-actuator-v5`, after recorded developer integration repairs;
the ensuing CAM passed full machine verification and target-stock comparison.
