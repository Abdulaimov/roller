"""Roofs: the white stone crown of the slab blocks, the perforated screen of the glass tower."""
import math

from shapely.geometry import Polygon
from shapely.ops import unary_union

from complex.geom import resample, ring_coords


def build_roof(mb, b, plan, zr):
    enc = Polygon(plan['enclosure']).buffer(0)
    if b['style'] == 'glass':
        from . import tower_a
        tower_a.build_roof(mb, b, plan, zr)
    else:
        from . import slab
        slab.build_roof(mb, b, plan, zr)
    # the facade lighting at night (the viewer shows it at dusk and at night)
    from .night import night_lights
    night_lights(mb, b, plan, zr)


def plant_rooms(mb, plan, zr, mat):
    """Lift machine rooms over the stair / lift halls."""
    for c in plan['common']:
        g = Polygon(c).buffer(0)
        if g.area < 15:
            continue
        x0, y0, x1, y1 = g.bounds
        w, d = min(x1 - x0 + 1.0, 12.0), min(y1 - y0 + 1.0, 9.0)
        cx, cy = g.centroid.x, g.centroid.y
        mb.box(cx, cy, zr, w, d, 3.2, mat)
        mb.box(cx, cy, zr + 3.2, w + 0.3, d + 0.3, 0.25, 'Stone white')


def brick_roof(mb, b, enc, plan, zr):
    outer = enc.buffer(0.14, join_style='mitre')
    mb.prism(outer, zr - 0.2, zr + 0.3, 'Stone white', None, 'Stone white')
    inner = enc.buffer(-0.4, join_style='mitre')
    mb.polygon_face(inner, zr + 0.31, 'Roof')
    ring = outer.difference(inner)
    mb.prism(ring, zr + 0.3, zr + 1.3, 'Stone white', 'Stone white')
    plant_rooms(mb, plan, zr + 0.3, 'Stone white')
    # the crown: white fins standing up from the parapet, a ring beam on top of them
    pts = resample(ring_coords(enc.buffer(0.05, join_style='mitre')), 3.3)
    n = len(pts)
    for i, p in enumerate(pts):
        q = pts[(i + 1) % n]
        rot = math.atan2(q[1] - p[1], q[0] - p[0])
        tall = 4.0 if i % 3 == 0 else 3.2
        mb.box(p[0], p[1], zr + 1.3, 0.4, 0.8, tall, 'Stone white', rot=rot)
    from .towers import pilasters
    pilasters(mb, enc, zr - 0.2, zr + 4.75)   # the white pilasters run up through the crown
    beam = enc.buffer(0.3, join_style='mitre').difference(enc.buffer(-0.35, join_style='mitre'))
    mb.prism(beam, zr + 4.4, zr + 4.75, 'Stone white', 'Stone white', 'Stone white')
    # a few condensers on the roof
    x0, y0, x1, y1 = inner.bounds
    for k in range(10):
        x = x0 + 3 + (x1 - x0 - 6) * ((k * 0.37) % 1)
        y = y0 + 2 + (y1 - y0 - 4) * ((k * 0.61) % 1)
        if inner.buffer(-1).contains(Polygon([(x - 0.6, y - 0.4), (x + 0.6, y - 0.4), (x + 0.6, y + 0.4), (x - 0.6, y + 0.4)])):
            mb.box(x, y, zr + 0.31, 1.2, 0.8, 0.9, 'Metal')


def glass_roof(mb, enc, zr):
    outer = enc.buffer(0.12, join_style='mitre')
    mb.prism(outer, zr - 0.22, zr + 0.5, 'White band', None, 'White band')
    inner = enc.buffer(-0.4, join_style='mitre')
    mb.polygon_face(inner, zr + 0.51, 'Roof')
    mb.prism(outer.difference(inner), zr + 0.5, zr + 1.2, 'White band', 'White band')
    # plant in the middle
    c = enc.centroid
    mb.box(c.x, c.y, zr + 0.5, 16.0, 12.0, 4.0, 'Plant room')
    # the crown: a perforated metal screen on a steel grid, rising from 6 to 9 m towards one corner
    ring = resample(ring_coords(enc.buffer(0.6, join_style='mitre')), 1.5)
    x0, y0, x1, y1 = enc.bounds
    # highest over the south-west corner, sloping down to the north-east (renders 1, 2 and 4)
    top = lambda p: zr + 1.2 + 4.0 + 6.5 * (1 - ((p[0] - x0) / (x1 - x0) + (p[1] - y0) / (y1 - y0)) / 2)
    zs0 = [zr + 1.2] * len(ring)
    zs1 = [top(p) for p in ring]
    mb.ribbon_z(ring + ring[:1], zs0 + zs0[:1], zs1 + zs1[:1], 'Mesh screen', double=True)
    for p, z in zip(ring, zs1):
        mb.box(p[0], p[1], zr + 1.2, 0.12, 0.12, z - zr - 1.2, 'Frame light')
    for frac in (0.33, 0.66, 1.0):
        zz = [zr + 1.2 + (z - zr - 1.2) * frac for z in zs1]
        mb.tube(ring, [v - 0.08 for v in zz], zz, 0.14, 'Frame light', closed=True)
