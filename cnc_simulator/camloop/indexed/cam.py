"""Compile agent-selected CAM parameters into explicit indexed movements."""
import copy,math
import numpy as np
from cncsim.geometry import InputError,keys,number
from cncsim.indexing import world_points
from cncsim.simulator import validate
from ..common import digest,file_hash

BASELINE=dict(stepover_fraction=.35,stepdown_mm=6,cut_feed_mm_min=350,plunge_feed_mm_min=120,retract_feed_mm_min=700,segments_per_circle=48,order='orientation',retract_mode='park',shortest_c=False)


def validate_strategy(strategy,job):
    keys(strategy,list(BASELINE))
    for k in ['stepover_fraction','stepdown_mm','cut_feed_mm_min','plunge_feed_mm_min','retract_feed_mm_min']:number(strategy[k],k,positive=True)
    if not .15<=strategy['stepover_fraction']<=.95:raise InputError('stepover_fraction must be in [.15,.95]')
    if not 1<=strategy['stepdown_mm']<=job['limits']['max_stepdown_mm']:raise InputError('stepdown exceeds fixed range')
    for k in ['cut_feed_mm_min','plunge_feed_mm_min','retract_feed_mm_min']:
        if strategy[k]>job['limits'][k]:raise InputError(k+' exceeds fixed ceiling')
    if type(strategy['segments_per_circle']) is not int or not 24<=strategy['segments_per_circle']<=96:raise InputError('segments_per_circle must be an integer in [24,96]')
    if strategy['order'] not in ['orientation','tool']:raise InputError('unsupported operation order')
    if strategy['retract_mode'] not in ['clearance','park']:raise InputError('unsupported retract_mode')
    if type(strategy['shortest_c']) is not bool:raise InputError('shortest_c must be boolean')


def verify_job(job):
    for kind in ['target','stock']:
        if file_hash(job['plan'][kind]['path'])!=job[kind+'_sha256']:raise InputError('Frozen '+kind+' changed')


def capsule_contour(a,b,r,segments):
    direction=b-a;length=np.linalg.norm(direction)
    angle=math.atan2(direction[1],direction[0]) if length else 0
    if length<1e-9:
        return [a+r*np.array([math.cos(t),math.sin(t)]) for t in np.linspace(0,2*math.pi,segments+1)]
    out=[]
    for center,start in [(b,angle-math.pi/2),(a,angle+math.pi/2)]:
        out.extend(center+r*np.array([math.cos(t),math.sin(t)]) for t in np.linspace(start,start+math.pi,segments//2+1))
    out.append(out[0]);return out


def compile_plan(job,strategy):
    validate_strategy(strategy,job);verify_job(job)
    p=copy.deepcopy(job['plan']);moves=[];phases=[];pose=np.array(p['initial_position'],float);bc=np.array([0.,0.]);tool=p['initial_tool']
    features=list(enumerate(job['features']))
    key=(lambda item:(item[1]['bc'],item[1]['tool'],item[0])) if strategy['order']=='orientation' else (lambda item:(item[1]['tool'],item[1]['bc'],item[0]))
    features.sort(key=key)
    def move(kind,to,feed=None):
        nonlocal pose
        to=np.asarray(to,float)
        if np.linalg.norm(to-pose)<1e-9:return
        m=dict(type=kind,to=np.round(to,7).tolist())
        if kind=='cut':m['feed_mm_per_min']=feed
        moves.append(m);pose=to.copy()
    def park():move('rapid',p['initial_position'])
    def index(next_bc):
        nonlocal bc
        next_bc=np.array(next_bc,float)
        if strategy['shortest_c']:next_bc[1]+=360*round((bc[1]-next_bc[1])/360)
        if np.max(np.abs(next_bc-bc))>1e-8:
            park();moves.append(dict(type='index',b_degrees=float(next_bc[0]),c_degrees=float(next_bc[1])));bc=next_bc
    for feature_index,f in features:
        phases.append(dict(move=len(moves),name=f['name'],feature=feature_index))
        index(f['bc'])
        if tool!=f['tool']:
            park();moves.append(dict(type='tool_change',tool=f['tool']));tool=f['tool']
        a,b=world_points(np.array([f['a'],f['b']]),bc,p['indexing'])
        radius=p['tools'][tool]['diameter_mm']/2;offset=max(0,f['radius']-radius)
        top=f['surface_z'];clearance=top+8
        # At an unchanged orientation, a common clearance plane is above all stock.
        move('rapid',[pose[0],pose[1],max(clearance,pose[2])]);move('rapid',[a[0],a[1],clearance])
        depths=list(np.arange(top-strategy['stepdown_mm'],a[2],-strategy['stepdown_mm']))+[float(a[2])]
        radii=list(np.arange(radius*2*strategy['stepover_fraction'],offset, radius*2*strategy['stepover_fraction']))
        if offset>1e-9:radii.append(offset)
        for depth in depths:
            move('cut',[a[0],a[1],depth],strategy['plunge_feed_mm_min'])
            move('cut',[b[0],b[1],depth],strategy['cut_feed_mm_min'])
            for r in radii:
                for xy in capsule_contour(a[:2],b[:2],r,strategy['segments_per_circle']):move('cut',[*xy,depth],strategy['cut_feed_mm_min'])
            move('cut',[a[0],a[1],depth],strategy['cut_feed_mm_min'])
        move('cut',[pose[0],pose[1],clearance],strategy['retract_feed_mm_min'])
        if strategy['retract_mode']=='park':park()
    park();index([0,0]);park();p['moves']=moves
    if len(moves)>15000:raise InputError('CAM movement budget exceeded')
    validate(p)
    return p,phases


def cheap_checks(job,plan):
    verify_job(job);validate(plan)
    if digest({k:v for k,v in plan.items() if k!='moves'})!=digest({k:v for k,v in job['plan'].items() if k!='moves'}):raise InputError('CAM changed fixed inputs')
    issues=[];mount=np.array(plan['indexing']['head_mount_mm']);gauge=np.array([0,0,plan['indexing']['gauge_length_mm']])
    for i,m in enumerate(plan['moves']):
        if 'to' in m:
            xyz=np.array(m['to'])+gauge-mount
            if np.any(xyz<plan['travel_limits']['min']) or np.any(xyz>plan['travel_limits']['max']):issues.append(dict(code='axis_overtravel',moves=[i],description='Machine XYZ exceeds fixed limits'))
        if m['type']=='index' and not -35<=m['b_degrees']<=110:issues.append(dict(code='b_overtravel',moves=[i],description='B exceeds machine range'))
    if plan['moves'][-1].get('to',plan['initial_position'])!=plan['initial_position']:
        # A final zero-motion index may follow park; verify the latest linear endpoint.
        last=next(m['to'] for m in reversed(plan['moves']) if 'to' in m)
        if last!=plan['initial_position']:issues.append(dict(code='return_position',moves=[],description='Did not return to fixed park'))
    return issues
