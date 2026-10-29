"""The two shop floors under all three blocks (render 6 and the developer's model): double-height
shop windows between grey stone piers, warm wood panels here and there, a dark band at the second
floor, the shops lit inside (floor, ceiling, back wall a few metres in), and on top of the podium a
terrace with a glass railing where no block stands.

The outline is everything drawn on the sheet of floor 2 (tools/rp/frame.py), in site metres.
"""
import math
import random

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from complex.geom import MeshBuilder, make_object
from complex.towers import add_rails

from .config import GROUND, SECOND, sheet_to_site

TOP = GROUND + SECOND
BAY = 3.3


def outline(fr):
    g = unary_union([Polygon([sheet_to_site(x, y) for x, y in p]).buffer(0) for p in fr['floor2']])
    g = g.buffer(0.8, join_style='mitre').buffer(-0.8, join_style='mitre')
    g = max(getattr(g, 'geoms', [g]), key=lambda q: q.area)
    return g.simplify(0.25)


def build(mats, col, fr, towers_fp):
    O = outline(fr)
    mb = MeshBuilder()
    inner = O.buffer(-4.2, join_style='mitre')
    # inside the glass: floors, lit ceilings, a back wall
    strip = O.buffer(-0.35, join_style='mitre').difference(inner)
    for z0, z1 in ((0.0, GROUND), (GROUND, TOP)):
        mb.polygon_face(strip, z0 + 0.03, 'Shop floor')
        mb.polygon_face(strip, z1 - 0.45, 'Shop ceiling', up=False)
        mb.prism(inner, z0 + 0.03, z1 - 0.45, 'Shop wall')
    # the solid core above the shop ceilings and between the floors
    mb.prism(O.buffer(-0.05, join_style='mitre'), GROUND - 0.45, GROUND + 0.05, 'Stone dark', None, 'Shop ceiling')
    # facade: piers, glass, the band at the second floor, wood panels
    ring = list(O.exterior.coords)
    for a, b in zip(ring[:-1], ring[1:]):
        L = math.dist(a, b)
        if L < 0.6:
            continue
        u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        n = (u[1], -u[0])   # outward (counter-clockwise ring)
        if not O.exterior.is_ccw:
            n = (-n[0], -n[1])
        rot = math.atan2(u[1], u[0])
        k = max(1, round(L / BAY))
        step = L / k
        # piers: dark stone; every third one (and the corners) broad and clad in wood boards
        # (render 6: wood-clad pillars between the dark-framed shop windows)
        for i in range(k + 1):
            s = i * step
            p = (a[0] + u[0] * s - n[0] * 0.15, a[1] + u[1] * s - n[1] * 0.15)
            if i % 3 == 0:
                mb.box(p[0], p[1], 0.0, 0.9, 0.56, TOP - 0.45, 'Podium wood', rot=rot)
                for t in (-0.3, -0.1, 0.1, 0.3):   # the boards' joints
                    q = (p[0] + u[0] * t - n[0] * 0.285, p[1] + u[1] * t - n[1] * 0.285)
                    mb.box(q[0], q[1], 0.0, 0.015, 0.01, TOP - 0.45, 'Shop frame', rot=rot)
            else:
                mb.box(p[0], p[1], 0.0, 0.55, 0.5, TOP, 'Stone dark', rot=rot)
        for i in range(k):
            s0, s1 = i * step + (0.45 if i % 3 == 0 else 0.28), (i + 1) * step - (0.45 if (i + 1) % 3 == 0 else 0.28)
            w = s1 - s0
            if w < 0.4:
                continue
            m = (a[0] + u[0] * (s0 + s1) / 2 - n[0] * 0.3, a[1] + u[1] * (s0 + s1) / 2 - n[1] * 0.3)
            for z0, z1 in ((0.0, GROUND - 0.45), (GROUND + 0.6, TOP - 0.1)):
                mb.box(m[0], m[1], z0, w, 0.03, z1 - z0, 'Shop glass', rot=rot)
                for zz in (z0, z1 - 0.07, z0 + 2.9 if z1 - z0 > 3.5 else None):
                    if zz is not None:
                        mb.box(m[0], m[1], zz, w, 0.08, 0.07, 'Shop frame', rot=rot)
                for t in (-w / 4, w / 4):
                    mb.box(m[0] + u[0] * t, m[1] + u[1] * t, z0, 0.06, 0.08, z1 - z0, 'Shop frame', rot=rot)
            # the dark band at floor 2
            mb.box(m[0] + n[0] * 0.05, m[1] + n[1] * 0.05, GROUND - 0.45, w + 0.6, 0.3, 1.05, 'Stone dark', rot=rot)
    # the podium's roof: a terrace where no block stands, a projecting white edge, a glass railing
    roof = O.difference(towers_fp.buffer(0.05, join_style='mitre'))
    # the canopy round the podium (render 6): a white slab a metre out, lights in its soffit
    mb.prism(O.buffer(1.0, join_style='mitre'), TOP - 0.45, TOP + 0.1, 'White band', None, 'White band')
    eave = O.buffer(0.55, join_style='mitre').exterior
    for k2 in range(int(eave.length / 1.6)):
        p = eave.interpolate(k2 * 1.6 + 0.8)
        if towers_fp.buffer(0.3).contains(p):
            continue
        mb.box(p.x, p.y, TOP - 0.47, 0.16, 0.16, 0.02, 'Night white')
    for q in getattr(roof, 'geoms', [roof]):
        if q.geom_type == 'Polygon' and q.area > 2:
            mb.polygon_face(q, TOP + 0.11, 'Deck paving')
    edge = O.buffer(0.45, join_style='mitre').exterior
    segs = []
    pts = list(edge.coords)
    for a, b in zip(pts[:-1], pts[1:]):
        mid = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if towers_fp.buffer(0.8).contains(mid):
            continue
        segs.append([a, b])
    add_rails(mb, segs, TOP + 0.1, post_step=0)
    ob = make_object('Podium', mb.to_mesh('Podium', mats), col)
    return O, ob
