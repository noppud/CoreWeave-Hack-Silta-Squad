"""Independent CAD targets and fixed manufacturing contracts for ten distinct parts."""
import copy
from pathlib import Path
import numpy as np
import trimesh
from cncsim.indexing import world_points, rotation
from ..common import save, file_hash

INDEXING = dict(pivot_mm=[0,-453.5294968,50.8],work_offset_mm=[0,0,40],initial_bc_degrees=[0,0],b_limits_degrees=[-35,110],degrees_per_second=30,settle_seconds=1,head_mount_mm=[330,254,618.89],gauge_length_mm=120)
TOOLS={name:dict(diameter_mm=d,flute_length_mm=60,shaft_diameter_mm=d,shaft_length_mm=30,holder_diameter_mm=40,holder_length_mm=30) for name,d in [('T12',12),('T8',8)]}

def top(name,a,b,r,floor):
    return dict(name=name,bc=[0,0],a=[*a,floor],b=[*b,floor],radius=r)

def side(name,angle,y,z0,z1,r,depth):
    rot=trimesh.transformations.rotation_matrix(np.radians(angle),[0,0,1])[:3,:3]
    return dict(name=name,bc=[90,angle],a=(rot@np.array([depth,y,z0])).tolist(),b=(rot@np.array([depth,y,z1])).tolist(),radius=r)

def ring_holes(radius,count,height,hole=4):
    return [top(f'Flange hole {i+1}',[radius*np.cos(a),radius*np.sin(a)],[radius*np.cos(a),radius*np.sin(a)],hole,height-10) for i,a in enumerate(np.linspace(0,2*np.pi,count,endpoint=False))]

def catalog():
    parts=[]
    def add(id,name,stock,features,split):parts.append(dict(id=id,name=name,stock_shape=stock,features=features,split=split))
    features=[top('Central cavity',[0,0],[0,0],23,9)]
    for a in range(0,360,90):
        for y in [-6,0,6]:features.append(side(f'Face {a} recess {y}',a,y,15,39,6,30))
        features.append(side(f'Face {a} window',a,0,23,31,6,18))
    add('01-actuator-housing','Actuator housing',dict(kind='cylinder',radius=36,height=50),features+ring_holes(29,4,50),'development')
    features=[top('Main gallery',[-13,0],[13,0],11,15),top('Control port',[0,17],[0,17],6,24)]
    for a in [0,90,180,270]:features.append(side(f'Cross port {a}',a,0,24,24,7,9))
    add('02-hydraulic-manifold','Hydraulic manifold',dict(kind='box',size=[66,56,46]),features,'development')
    features=[top('Bearing seat',[0,0],[0,0],19,8),top('Counterbore',[0,0],[0,0],24,36)]
    features += [side('Side oil passage',0,0,21,21,5,14),side('Mounting slot',90,0,18,27,6,21)]
    add('03-bearing-block','Bearing block',dict(kind='box',size=[62,62,48]),features,'held_out')
    features=[top('Cage cavity',[0,0],[0,0],24,8)]
    for a in range(0,360,60):features.append(side(f'Cage window {a}',a,0,20,34,7,18))
    add('04-trunnion-cage','Six-window trunnion cage',dict(kind='cylinder',radius=34,height=50),features,'held_out')
    features=[top('Sleeve bore',[0,0],[0,0],16,7)]+ring_holes(26,6,30)
    features += [side('Radial keyway',0,0,12,20,5,24),side('Lock port',180,0,15,15,4,12)]
    add('05-flanged-sleeve','Flanged instrument sleeve',dict(kind='cylinder',radius=34,height=30),features,'held_out')
    features=[top('Electronics cavity',[-11,0],[11,0],17,8),side('Cable port',0,0,23,23,7,15),side('Connector slot',90,0,18,27,5,18)]
    add('06-sensor-enclosure','Sensor enclosure',dict(kind='box',size=[70,54,42]),features,'held_out')
    features=[top('Valve chamber',[0,0],[0,0],14,8),top('Seal seat',[0,0],[0,0],19,38)]
    for a in [0,120,240]:features.append(side(f'Valve port {a}',a,0,24,24,8,8))
    add('07-valve-body','Three-way valve body',dict(kind='cylinder',radius=35,height=48,sections=6),features,'held_out')
    features=[top('Motor register',[0,0],[0,0],22,8)]+ring_holes(29,4,30)
    features += [side('Mount recess',0,-5,13,18,5,27),side('Mount recess rear',180,5,13,18,5,27)]
    add('08-motor-mount','Motor mounting flange',dict(kind='cylinder',radius=36,height=30),features,'held_out')
    features=[top('Left bearing pocket',[-16,0],[-16,0],14,8),top('Right bearing pocket',[16,0],[16,0],14,12),side('Lubrication passage',90,0,17,17,5,8)]
    add('09-gearbox-cover','Dual-bearing gearbox cover',dict(kind='box',size=[72,48,32]),features,'held_out')
    features=[top('Optical seat',[-7,0],[7,0],13,12),side('Front window',0,0,22,34,9,11),side('Cross mounting slot',90,0,20,29,6,15)]
    add('10-optical-bracket','Optical instrument bracket',dict(kind='box',size=[58,48,48]),features,'held_out')
    return parts


def stock_mesh(spec):
    h=spec.get('height',spec.get('size',[0,0,0])[2])
    mesh=trimesh.creation.cylinder(radius=spec['radius'],height=h,sections=spec.get('sections',96)) if spec['kind']=='cylinder' else trimesh.creation.box(spec['size'])
    mesh.apply_translation([0,0,h/2]);return mesh


def feature_cut(feature,stock,indexing):
    a,b=world_points(np.array([feature['a'],feature['b']]),feature['bc'],indexing)
    high=world_points(stock.vertices,feature['bc'],indexing)[:,2].max()+20
    height=high-a[2];r=feature['radius']
    solids=[]
    for center in [a,b]:
        c=trimesh.creation.cylinder(radius=r,height=height,sections=64)
        c.apply_translation([center[0],center[1],a[2]+height/2]);solids.append(c)
    length=np.linalg.norm(b[:2]-a[:2])
    if length>1e-8:
        box=trimesh.creation.box([length,2*r,height]);angle=np.arctan2(b[1]-a[1],b[0]-a[0]);box.apply_transform(trimesh.transformations.rotation_matrix(angle,[0,0,1]));box.apply_translation([(a[0]+b[0])/2,(a[1]+b[1])/2,a[2]+height/2]);solids.append(box)
    mesh=trimesh.boolean.union(solids,engine='manifold')
    origin=world_points(np.zeros((1,3)),feature['bc'],indexing)[0]
    mesh.vertices=(mesh.vertices-origin)@rotation(feature['bc'])
    return mesh


def prepare(root):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    if (root/'catalog.json').exists():raise ValueError('Refusing to overwrite a frozen benchmark')
    entries=[]
    for part in catalog():
        directory=root/'parts'/part['id'];directory.mkdir(parents=True,exist_ok=False)
        stock=stock_mesh(part['stock_shape']);target=trimesh.boolean.difference([stock,trimesh.boolean.union([feature_cut(f,stock,INDEXING) for f in part['features']],engine='manifold')],engine='manifold')
        if not target.is_volume:raise ValueError('Invalid target '+part['id'])
        stock.export(directory/'stock.stl');target.export(directory/'target.stl')
        plan=dict(units='mm',target=dict(type='mesh',path=str(directory/'target.stl')),stock=dict(type='mesh',path=str(directory/'stock.stl')),fixtures=[dict(type='box',min=[-18,-18,-40],max=[18,18,0])],tools=copy.deepcopy(TOOLS),travel_limits=dict(min=[-762,-508,-508],max=[0,0,63.5]),initial_position=[0,0,180],initial_tool='T12',moves=[],tolerance_mm=3.0,resolution_mm=1.0,max_cells=2000000,rapid_mm_per_min=6000,tool_change_seconds=15,indexing=copy.deepcopy(INDEXING))
        for f in part['features']:
            f['tool']='T12' if f['radius']>=6 else 'T8'
            f['surface_z']=float(world_points(stock.vertices,f['bc'],INDEXING)[:,2].max())
        part.update(plan=plan,target_sha256=file_hash(directory/'target.stl'),stock_sha256=file_hash(directory/'stock.stl'),target_volume_mm3=float(target.volume),stock_volume_mm3=float(stock.volume),limits=dict(cut_feed_mm_min=900,plunge_feed_mm_min=250,retract_feed_mm_min=1200,max_stepdown_mm=12))
        save(directory/'job.json',part);entries.append(dict(id=part['id'],name=part['name'],split=part['split'],job=str(directory/'job.json')))
        print('Frozen',part['id'],flush=True)
    save(root/'catalog.json',dict(parts=entries,objective='estimated machining seconds; geometry and configured collisions are pass/fail',machine='Haas UMC-750 Reboot; indexed 3+2',learning_split='Two development parts; eight held-out geometries unseen by learning prompts before guidance freeze'))
    return entries
