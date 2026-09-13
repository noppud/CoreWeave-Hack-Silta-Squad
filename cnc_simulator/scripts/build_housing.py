"""Frozen multi-face housing and deterministic indexed CAM seed; dimensions in mm."""
import json
from pathlib import Path
import numpy as np
import trimesh
from cncsim.indexing import world_points

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'examples'/'indexed-housing'
OUT.mkdir(parents=True,exist_ok=True)
indexing = dict(pivot_mm=[0,-453.5294968,50.8],work_offset_mm=[0,0,40], initial_bc_degrees=[0,0],b_limits_degrees=[-35,110],degrees_per_second=30,settle_seconds=1,head_mount_mm=[330,254,618.89],gauge_length_mm=120)


def cylinder(radius,low,high):
    return trimesh.creation.cylinder(radius=radius,height=high-low,sections=96,transform=trimesh.transformations.translation_matrix([0,0,(high+low)/2]))


def capsule(y,z0,z1,r,depth,angle):
    # Extruded capsule along radial +X, independently specified design feature.
    length=75-depth
    c=trimesh.creation.cylinder(radius=r,height=length,sections=48)
    c.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[0,1,0]))
    c1=c.copy();c1.apply_translation([(75+depth)/2,y,z0])
    c2=c.copy();c2.apply_translation([(75+depth)/2,y,z1])
    box=trimesh.creation.box([length,2*r,z1-z0]);box.apply_translation([(75+depth)/2,y,(z0+z1)/2])
    result=trimesh.boolean.union([c1,c2,box],engine='manifold')
    result.apply_transform(trimesh.transformations.rotation_matrix(np.radians(angle),[0,0,1]))
    return result

stock=cylinder(50,0,80)
subtract=[cylinder(34,12,90)]
for angle in range(0,360,45):
    # Sculpted face: three overlapping capsule recesses, then a deeper opening.
    for y in [-10,0,10]: subtract.append(capsule(y,20,64,6,44,angle))
    subtract.append(capsule(0,32,52,6,29,angle))
    hole=cylinder(2.5,68,90)
    hole.apply_translation([42*np.cos(np.radians(angle)),42*np.sin(np.radians(angle)),0])
    subtract.append(hole)
print('Building frozen target',flush=True)
target=trimesh.boolean.difference([stock,trimesh.boolean.union(subtract,engine='manifold')],engine='manifold')
assert target.is_volume
stock.export(OUT/'stock.stl');target.export(OUT/'target.stl')
plan=dict(units='mm',target=dict(type='mesh',path='target.stl'),stock=dict(type='mesh',path='stock.stl'),fixtures=[dict(type='box',min=[-30,-30,-40],max=[30,30,0])],tools={'T12':dict(diameter_mm=12,flute_length_mm=70,shaft_diameter_mm=12,shaft_length_mm=20,holder_diameter_mm=40,holder_length_mm=30),'T5':dict(diameter_mm=5,flute_length_mm=20,shaft_diameter_mm=5,shaft_length_mm=70,holder_diameter_mm=40,holder_length_mm=30)},travel_limits=dict(min=[-762,-508,-508],max=[0,0,63.5]),initial_position=[0,0,210],initial_tool='T12',moves=[],tolerance_mm=4.5,resolution_mm=1.5,max_cells=2000000,rapid_mm_per_min=6000,tool_change_seconds=15,indexing=indexing)
phase=[];bc=[0,0]
def move(kind,to,feed=600):
    m=dict(type=kind,to=[round(float(v),6) for v in to])
    if kind=='cut':m['feed_mm_per_min']=feed
    plan['moves'].append(m)
def local(p):return world_points(np.array([p]),bc,indexing)[0]
def cut(p,feed=600):move('cut',local(p),feed)
def rapid(p):move('rapid',local(p))
def stage(name):phase.append(dict(move=len(plan['moves']),name=name))
stage('Open central cavity')
# Helical-like stepped circular contours, then raster; no unsupported arc commands.
for depth in [68,56,44,32,20,12]:
    rapid([0,0,90]);cut([0,0,depth],180)
    for radius in [6,12,18,24,28]:
        for a in np.linspace(0,2*np.pi,37):cut([radius*np.cos(a),radius*np.sin(a),depth])
    cut([28,0,90],1000)
move('rapid',[0,0,210])
for angle in range(0,360,45):
    stage(f'Index and machine face {angle//45+1}')
    plan['moves'].append(dict(type='index',b_degrees=90,c_degrees=angle))
    bc=[90,angle]
    # Program in each radial face's local frame then map to stationary spindle.
    rot=trimesh.transformations.rotation_matrix(np.radians(angle),[0,0,1])[:3,:3]
    def face(p):return rot@np.array(p)
    for y in [-10,-5,0,5,10]:
        rapid(face([65,y,20]));cut(face([44,y,20]),180);cut(face([44,y,64]));cut(face([65,y,64]),1000)
    for depth in [44,36,29]:
        rapid(face([65,0,32]));cut(face([depth,0,32]),180);cut(face([depth,0,52]));cut(face([65,0,52]),1000)
    move('rapid',[0,0,210])
stage('Index to top and machine flange holes')
plan['moves'].append(dict(type='index',b_degrees=0,c_degrees=0));bc=[0,0]
plan['moves'].append(dict(type='tool_change',tool='T5'))
for angle in range(0,360,45):
    x,y=42*np.cos(np.radians(angle)),42*np.sin(np.radians(angle))
    rapid([x,y,90]);cut([x,y,68],100);cut([x,y,90],1000)
move('rapid',[0,0,210])
(OUT/'plan.json').write_text(json.dumps(plan,indent=2))
(OUT/'design.json').write_text(json.dumps(dict(name='Eight-face actuator housing',stock_radius_mm=50,stock_height_mm=80,cavity_radius_mm=34,cavity_floor_mm=12,faces=8,phases=phase,target_volume_mm3=target.volume,stock_volume_mm3=stock.volume,description='Reference-inspired demonstration geometry, not a reproduction or production-qualified part.'),indent=2))
print('Generated',len(plan['moves']),'moves;',len(target.faces),'target triangles',flush=True)
