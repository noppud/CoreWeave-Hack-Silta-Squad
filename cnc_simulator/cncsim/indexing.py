"""Indexed B/C table transforms. Rotation is allowed only with cutting disabled."""
import numpy as np
from .geometry import keys, number, vector, InputError


def validate_indexing(spec):
    keys(spec, ['pivot_mm', 'work_offset_mm', 'initial_bc_degrees', 'b_limits_degrees',
                'degrees_per_second', 'settle_seconds', 'head_mount_mm', 'gauge_length_mm'])
    for field in ['pivot_mm', 'work_offset_mm', 'head_mount_mm']:
        vector(spec[field], field)
    for field in ['initial_bc_degrees', 'b_limits_degrees']:
        if not isinstance(spec[field], list) or len(spec[field]) != 2:
            raise InputError(field + ' must contain two numbers')
        for x in spec[field]: number(x, field)
    if spec['b_limits_degrees'][0] >= spec['b_limits_degrees'][1]:
        raise InputError('B limits must increase')
    number(spec['degrees_per_second'], 'degrees_per_second', positive=True)
    number(spec['settle_seconds'], 'settle_seconds', nonnegative=True)
    number(spec['gauge_length_mm'], 'gauge_length_mm', positive=True)


def rotation(bc):
    """UMC table: C rotates about -Z, then B about -Y; angles in degrees."""
    b, c = np.radians(bc)
    cb, sb, cc, sc = np.cos(b), np.sin(b), np.cos(c), np.sin(c)
    return np.array([[cb,0,-sb],[0,1,0],[sb,0,cb]]) @ np.array([[cc,sc,0],[-sc,cc,0],[0,0,1]])


def world_points(points, bc, spec):
    # C pivot is the work table origin. B pivot is expressed in the same frame.
    b, c = bc
    pivot = np.asarray(spec['pivot_mm'])
    offset = np.asarray(spec['work_offset_mm'])
    return ((points + offset) @ rotation([0,c]).T - pivot) @ rotation([b,0]).T + pivot


def index_samples(points, start, end, spec, max_step_degrees=2):
    """Midpoint poses and a conservative ball bound on every point's motion.

    Sum of arc lengths bounds simultaneous B/C motion across each interval.
    Inflate collision tests by this distance: sampling cannot silently miss contact.
    """
    delta = np.asarray(end) - start
    count = max(1, int(np.ceil(np.max(np.abs(delta)) / max_step_degrees)))
    if count > 1000:
        raise InputError('Index motion exceeds 1000 collision intervals')
    offset = np.asarray(spec['work_offset_mm'])
    radius_c = np.max(np.linalg.norm(points + offset, axis=1))
    radius_b = radius_c + np.linalg.norm(spec['pivot_mm'])
    guard = (radius_b * abs(np.radians(delta[0])) + radius_c * abs(np.radians(delta[1]))) / (2*count)
    for i in range(count):
        yield world_points(points, np.asarray(start) + delta*(i+.5)/count, spec), guard
