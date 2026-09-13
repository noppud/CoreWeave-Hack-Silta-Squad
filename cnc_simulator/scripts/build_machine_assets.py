"""Package the downloaded-machine export and source-backed setup for offline viewing."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    config = json.loads((REPO / 'config/soft-jaw-job.json').read_text())
    source = HERE / 'assets/machine'
    machine = json.loads((source/'machine-raw.json').read_text())
    fixture = json.loads((source/'fixture-raw.json').read_text())
    target = json.loads((source/'target-raw.json').read_text())
    library = json.loads((REPO/'config/starter-tools-assembled.json').read_text())
    groups = {m['group'] for m in machine['meshes']}
    if groups != {'Static:1','X-Axis:1','Y-Axis:1','Z-Axis:1','Spindle:1'}:
        raise ValueError('Unexpected machine group inventory')
    provenance = []
    for path, expected in [
        ('research/assets/haas-vf-2.f3d',config['machine']['simulation_geometry']['sha256']),
        ('config/haas-vise-with-parallels-g54.f3d',config['setup']['fixture']['artifact']['sha256'] if 'setup' in config else None),
        ('config/starter-tools-assembled.json',config['tools']['library']['sha256']),
        ('config/haas-vf-2-linked.mch',config['machine']['definition']['sha256']),
    ]:
        actual = sha(REPO/path)
        if expected and actual != expected:
            raise ValueError(f'Pinned source changed: {path}')
        provenance.append(dict(path=path,sha256=actual,pinned=expected is not None))
    # Find the existing trusted setup block without importing Fusion at runtime.
    setup = next(v for v in config.values() if isinstance(v,dict) and 'machine_position' in v)
    tools = []
    for tool in library['data']:
        unit = 25.4 if tool['unit']=='inches' else 1
        holder_unit = 25.4 if tool['holder']['unit']=='inches' else 1
        geom = tool['geometry']
        gauge = geom['assemblyGaugeLength']*unit
        holder_gauge = tool['holder']['gaugeLength']*holder_unit
        tools.append(dict(number=tool['post-process']['number'],product_id=tool['product-id'],
            description=tool['description'],diameter_mm=geom['DC']*unit,
            flute_length_mm=geom['LCF']*unit,shaft_diameter_mm=geom['SFDM']*unit,
            stickout_mm=gauge-holder_gauge,gauge_length_mm=gauge,
            holder_product_id=tool['holder']['product-id'],holder_description=tool['holder']['description'],
            holder_segments=[dict(height=s['height']*holder_unit,lower_diameter=s['lower-diameter']*holder_unit,
                upper_diameter=s['upper-diameter']*holder_unit) for s in tool['holder']['segments']]))
    bundle = dict(name='Haas VF-2',units='mm',machine=machine,fixture=fixture,target=target,tools=tools,
        g54_translation_mm=setup['machine_position']['translation_mm'],
        kinematics=json.loads((REPO/'config/haas-vf-2-linked.mch').read_text())['kinematics']['default'],
        park_g54_mm=[0,0,50],provenance=provenance,
        export_hashes={name:sha(source/name) for name in ['machine-raw.json','fixture-raw.json','target-raw.json']},
        coverage='Reference setup only. Not included in pocket-demo collision verdicts. Tool profiles are library-derived envelopes; no full-machine verification.')
    destination=HERE/'viewer/dist/assets/haas-vf2.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(bundle,separators=(',',':'))+'\n')
    print(f'{len(machine["meshes"])} machine bodies, {len(fixture["meshes"])} fixture bodies, {len(tools)} tool assemblies -> {destination}')


if __name__=='__main__':
    build()
