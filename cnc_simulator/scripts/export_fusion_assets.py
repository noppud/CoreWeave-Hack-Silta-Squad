"""One-time read-only tessellation inside Fusion via the existing bridge.

Does not activate, import, save, close or edit documents. The simulator/viewer do
not import this script and do not depend on Fusion after asset conversion.
"""
# ruff: noqa: F821 -- app, adsk and payload are injected by the Fusion bridge.
import json
from pathlib import Path

output = Path(payload['output'])
output.mkdir(parents=True, exist_ok=True)
original_document = app.activeDocument.name
original_command = app.userInterface.activeCommand


def appearance(body):
    try:
        item = body.appearance
        colors = {}
        for prop in item.appearanceProperties:
            color = adsk.core.ColorProperty.cast(prop)
            if color:
                c = color.value
                colors[prop.id] = [c.red/255,c.green/255,c.blue/255]
        return {'name':item.name,'colors':colors}
    except Exception:
        return {'name':'unavailable','colors':{}}


def export_design(design, filename, occurrence_filter=None, include_children=True):
    meshes=[]
    def walk(component, transforms, ancestry):
        for body in component.bRepBodies:
            if not body.isVisible:
                continue
            calc=body.meshManager.createMeshCalculator()
            calc.surfaceTolerance=0.02  # 0.2 mm, visualization only
            mesh=calc.calculate()
            if not mesh:
                raise RuntimeError('Cannot tessellate '+body.name)
            points=[]
            for point in mesh.nodeCoordinates:
                for transform in reversed(transforms):
                    point.transformBy(transform)
                points.extend([point.x*10,point.y*10,point.z*10])
            meshes.append({'name':body.name,'group':ancestry[0] if ancestry else 'root',
                'path':'/'.join(ancestry+[body.name]),'positions':points,
                'indices':list(mesh.nodeIndices),'appearance':appearance(body)})
        if not include_children:
            return
        for occ in component.occurrences:
            if not occ.isVisible:
                continue
            if not ancestry and occurrence_filter and occ.name not in occurrence_filter:
                continue
            walk(occ.component,transforms+[occ.transform2],ancestry+[occ.name])
    walk(design.rootComponent,[],[])
    path=output / filename
    path.write_text(json.dumps({'units':'mm','document':design.parentDocument.name,'meshes':meshes},separators=(',',':')))
    return {'path':str(path),'bodies':len(meshes),'triangles':sum(len(m['indices'])//3 for m in meshes),'groups':list(dict.fromkeys(m['group'] for m in meshes))}

machine=None
fixture=None
for doc in app.documents:
    design=adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    if design and doc.name=='Silta VF2 simulation model':
        machine=design
    # Prepared archive already open, before it was imported into CAM assemblies.
    if design and design.rootComponent.bRepBodies.count==0:
        names=[o.name for o in design.rootComponent.occurrences]
        if len(names)==19 and 'Haas 09-0108 parallel envelope 1:1' in names:
            fixture=design
if machine is None:
    raise RuntimeError('Expected already-open linked VF2 model; no automatic document switching')
result={'machine':export_design(machine,'machine-raw.json')}
if fixture:
    result['fixture']=export_design(fixture,'fixture-raw.json')
active_design=adsk.fusion.Design.cast(app.activeDocument.products.itemByProductType('DesignProductType'))
if active_design and active_design.rootComponent.bRepBodies.count==1:
    result['target']=export_design(active_design,'target-raw.json',include_children=False)
result['active_document_unchanged']=app.activeDocument.name==original_document
result['active_command_unchanged']=app.userInterface.activeCommand==original_command
(output/'export-receipt.json').write_text(json.dumps(result,indent=2))
