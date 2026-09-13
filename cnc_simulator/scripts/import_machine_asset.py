"""One-time imported machine tessellation via the existing Fusion bridge.

Imports a separate machine document and restores the previously active document. The simulator/viewer do
not import this script and do not depend on Fusion after asset conversion.
"""
# ruff: noqa: F821 -- app, adsk and payload are injected by the Fusion bridge.
import json
from pathlib import Path

output = Path(payload['output'])
output.mkdir(parents=True, exist_ok=True)
original_doc = app.activeDocument
original_document = original_doc.name
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

options=app.importManager.createFusionArchiveImportOptions(payload['archive'])
doc=app.importManager.importToNewDocument(options)
try:
    design=adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    result=export_design(design,'machine-raw.json')
    result['source_archive']=payload['archive']
finally:
    original_doc.activate()
result['active_document_restored']=app.activeDocument.name==original_document
(output/'export-receipt.json').write_text(json.dumps(result,indent=2))
