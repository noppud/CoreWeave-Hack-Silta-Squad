"""Narrow cutter endpoint checks; no swept-volume or manufacturing certification.

Preserves the prepared-parallel check and adds finished-side protection only
for the explicit pre-sized blank/internal-features-only setup contract.
Unsupported NC modes or setups are outside coverage; passing is not approval.
"""
import hashlib
import json
import math
import re

FIXTURE = '95089aef15dd1e52bb91f9466723a1c00ed1716b00ed14fdb725a81c98a61936'
POST = '7793e1d36e12c63e61535f112fddb570076058820839b9459f736cf40e36c3c4'
FRAME = 'G54 stock top center; fixture already positioned relative to accepted part. Import at identity, do not re-close or re-position individual jaw components.'
INTERNAL_ONLY = 'Assume pre-sized AL6061 jaw blank meets finished outer dimensions and drawing tolerance before this job; mill internal obround features only. Deburring remains final manual step.'
BOXES = [((-76.2, -25.4, -63.5), (76.2, -12.7, -25.4)),
         ((-76.2, 12.7, -63.5), (76.2, 25.4, -25.4))]
WORD = re.compile(r'([A-Z])([+-]?(?:\d+(?:\.\d*)?|\.\d+))')
EPS = 0.005


def read_artifact(ref):
    with open(ref['path'], 'rb') as stream:
        content = stream.read()
    if hashlib.sha256(content).hexdigest() != ref['sha256']:
        raise ValueError('artifact SHA256 mismatch')
    return content


def endpoints(text):
    # Validate the entire supported lexical/mode subset before yielding.
    # No macros, cycles, subprograms, rotary axes, coordinate transforms,
    # incremental moves or cutter compensation. G53 positions are discarded.
    blocks = []
    allowed_g = {0, 1, 2, 3, 17, 20, 21, 40, 43, 49, 53, 54, 90, 94}
    allowed_m = {0, 1, 3, 4, 5, 6, 8, 9, 30}
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = re.sub(r'\([^()]*\)', '', raw.upper()).split(';', 1)[0].strip()
        if not line or line == '%':
            continue
        words = WORD.findall(line)
        if WORD.sub('', line).strip():
            return
        block = {}
        for letter, value in words:
            if letter not in 'NGMXYZIJKRFSTHO':
                return
            value = float(value)
            if not math.isfinite(value):
                return
            block.setdefault(letter, []).append(value)
        if any(len(v) > 1 for k, v in block.items() if k not in ('G', 'M')):
            return
        if not set(block.get('G', [])).issubset(allowed_g):
            return
        if not set(block.get('M', [])).issubset(allowed_m):
            return
        gs = block.get('G', [])
        if any(sum(g in group for g in gs) > 1 for group in
               ({0, 1, 2, 3}, {20, 21}, {43, 49})):
            return
        blocks.append((line_no, block))
    scale = None
    absolute = False
    plane = False
    wcs = False
    motion = None
    pending_tool = None
    tool = None
    length_offset = None
    pos = dict.fromkeys('XYZ')
    for line_no, b in blocks:
        gs = b.get('G', [])
        ms = b.get('M', [])
        if 90 in gs:
            absolute = True
        if 17 in gs:
            plane = True
        if 20 in gs or 21 in gs:
            new_scale = 25.4 if 20 in gs else 1.0
            if scale != new_scale:
                pos = dict.fromkeys('XYZ')
            scale = new_scale
        if 54 in gs:
            wcs = True
        if 'T' in b:
            pending_tool = b['T'][0]
        if 6 in ms:
            tool = pending_tool
            length_offset = None
            pos = dict.fromkeys('XYZ')
        if 49 in gs:
            length_offset = None
            pos['Z'] = None
        if 43 in gs:
            length_offset = b.get('H', [None])[0]
            pos['Z'] = None
        elif 'H' in b:
            return
        for g in gs:
            if g in (0, 1, 2, 3):
                motion = g
        if 53 in gs:
            pos = dict.fromkeys('XYZ')
            continue
        if not (absolute and plane and wcs and scale is not None):
            pos = dict.fromkeys('XYZ')
            continue
        for axis in 'XYZ':
            if axis in b:
                pos[axis] = b[axis][0] * scale
        if (any(a in b for a in 'XYZ') and motion in (0, 1, 2, 3)
                and tool is not None and length_offset == tool
                and all(pos[a] is not None for a in 'XYZ')):
            yield line_no, tool, tuple(pos[a] for a in 'XYZ')
        if 30 in ms:
            return


def finished_sides(setup, constraints):
    stock = setup.get('stock', {})
    if stock.get('precondition') != INTERNAL_ONLY:
        return None
    # This explicit scope is tied to the inspected blank and model orientation.
    if (stock.get('local_min_mm') != [-76.2, -25.4, -25.4]
            or stock.get('local_max_mm') != [76.2, 25.4, 0]
            or stock.get('dimensions_mm') != [152.4, 50.8, 25.4]
            or setup['work_coordinate_system'].get('axes') !=
            'X along152.4mm length,Y along50.8mm width,Z upward; right handed'):
        return None
    tol = float(constraints['tolerances']['linear_plus_minus_mm'])
    if not math.isfinite(tol) or tol < 0:
        raise ValueError('invalid linear tolerance')
    return stock['local_min_mm'], stock['local_max_mm'], tol


def side_overlap(x, y, z, radius, flute, scope):
    lo, hi, tol = scope
    # Require overlap well inside the stock's vertical interval. This avoids
    # rejecting clearance moves, bottom breakthrough or top-face tangency.
    if min(z + flute, hi[2] - tol) - max(z, lo[2] + tol) <= EPS:
        return None
    # Test a finite vertical side patch inset by the drawing tolerance.
    # Finding the patch strictly inside the cutter proves intrusion beyond
    # tolerance without interpreting arc sweeps or simulating stock removal.
    for axis, c, along, lower, upper, a0, a1 in (
            ('X', x, y, lo[0], hi[0], lo[1], hi[1]),
            ('Y', y, x, lo[1], hi[1], lo[0], hi[0])):
        if a1 - a0 <= 2 * tol or upper - lower <= 2 * tol:
            continue
        distance_along = max(a0 + tol - along, 0.0, along - (a1 - tol))
        for label, nominal, inset in (
                ('min', lower, lower + tol),
                ('max', upper, upper - tol)):
            # Both the nominal face and its tolerance-inset patch must be
            # inside the cutter. An internal pocket near a side is allowed.
            if (math.hypot(c - nominal, distance_along) < radius - EPS
                    and math.hypot(c - inset, distance_along) < radius - EPS):
                return axis + ' ' + label
    return None


def check(data: dict):
    issues = []
    try:
        constraints = data['constraints']
        setup = constraints['setup']
        fixture = setup.get('fixture', {})
        wcs = setup.get('work_coordinate_system', {})
        if (fixture.get('artifact', {}).get('sha256') != FIXTURE
                or fixture.get('coordinate_frame') != FRAME
                or wcs.get('name') != 'G54'
                or wcs.get('origin') != 'center of blank top face'
                or wcs.get('work_offset') != 1
                or constraints['machine'].get('axes') != 3):
            return {'passed': True, 'issues': []}
        candidate = data['candidate']
        artifacts = candidate['artifacts']
        analysis = json.loads(read_artifact(artifacts['analysis']))
        if analysis.get('input_digest') != data['input_digest']:
            raise ValueError('analysis input binding mismatch')
        if len(analysis.get('inspection', {}).get('setups', [])) != 1:
            return {'passed': True, 'issues': []}
        if analysis.get('postprocessor', {}).get('sha256') != POST:
            return {'passed': True, 'issues': []}
        scope = finished_sides(setup, constraints)
        cutters = {}
        ambiguous = set()
        for op in analysis['inspection']['operations']:
            t = op['tool']
            if t.get('type') != 'flat end mill':
                continue
            unit = {'inches': 25.4, 'millimeters': 1.0}.get(t.get('unit'))
            if unit is None:
                continue
            geometry = t['geometry']
            if float(geometry.get('RE', 0)) != 0:
                continue
            number = t['post-process']['number']
            shape = (float(geometry['DC']) * unit / 2,
                     float(geometry['LCF']) * unit)
            if not all(math.isfinite(v) and v > EPS for v in shape):
                continue
            if number in cutters and cutters[number] != shape:
                ambiguous.add(number)
            cutters[number] = shape
        nc_refs = [(k, v) for k, v in artifacts.items() if k.startswith('nc-')]
        if not nc_refs:
            raise ValueError('posted NC artifact missing')
        for name, ref in nc_refs:
            text = read_artifact(ref).decode('ascii')
            for line, tool, (x, y, z) in endpoints(text):
                if tool not in cutters or tool in ambiguous:
                    continue
                radius, flute = cutters[tool]
                prefix = (f'{name} line {line}: T{tool:g} cutter at '
                          f'G54 ({x:.3f}, {y:.3f}, {z:.3f}) mm ')
                for index, (lo, hi) in enumerate(BOXES, 1):
                    overlap_z = min(z + flute, hi[2]) - max(z, lo[2])
                    dx = max(lo[0] - x, 0.0, x - hi[0])
                    dy = max(lo[1] - y, 0.0, y - hi[1])
                    if overlap_z > EPS and math.hypot(dx, dy) < radius - EPS:
                        issues.append(prefix + 'overlaps prepared solid parallel '
                                      f'envelope {index}; endpoint-only check, '
                                      'not full simulation.')
                        break
                if scope is not None:
                    side = side_overlap(x, y, z, radius, flute, scope)
                    if side is not None:
                        issues.append(prefix + f'intersects finished {side} side '
                                      'beyond the linear tolerance under the '
                                      'pre-sized blank/internal-features-only '
                                      'contract; endpoint-only check.')
                if issues:
                    break
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        issues.append('Cutter endpoint check unavailable: ' + str(exc))
    return {'passed': not issues, 'issues': issues}
