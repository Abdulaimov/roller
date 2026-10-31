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

from .config import DOORS, GROUND, RAMP_X, SECOND, sheet_to_site

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
    # the ramp's door on кӯчаи Нарзиқулова (no shop window there)
    ramp = Polygon([sheet_to_site(x, y) for x, y in [(RAMP_X[0] - 0.6, 15.0), (RAMP_X[1] + 0.6, 15.0), (RAMP_X[1] + 0.6, 22.0), (RAMP_X[0] - 0.6, 22.0)]])
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
            if ramp.contains(Point(p)):
                continue
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
            if ramp.buffer(0.5).contains(Point(m)):
                continue
            for z0, z1 in ((0.0, GROUND - 0.45), (GROUND + 0.6, TOP - 0.1)):
                mb.box(m[0], m[1], z0, w, 0.03, z1 - z0, 'Shop glass', rot=rot)
                for zz in (z0, z1 - 0.07, z0 + 2.9 if z1 - z0 > 3.5 else None):
                    if zz is not None:
                        mb.box(m[0], m[1], zz, w, 0.08, 0.07, 'Shop frame', rot=rot)
                for t in (-w / 4, w / 4):
                    mb.box(m[0] + u[0] * t, m[1] + u[1] * t, z0, 0.06, 0.08, z1 - z0, 'Shop frame', rot=rot)
            # the dark band at floor 2
            mb.box(m[0] + n[0] * 0.05, m[1] + n[1] * 0.05, GROUND - 0.45, w + 0.6, 0.3, 1.05, 'Stone dark', rot=rot)
    # the ramp's door: a dark opening 3.4 m high, the stone over it to the band at floor 2, the
    # ramp's walls and its floor sloping down inside
    edge = O.exterior.intersection(ramp)
    if not edge.is_empty:
        ea, eb = Point(edge.coords[0] if edge.geom_type == 'LineString' else edge.geoms[0].coords[0]), Point(edge.coords[-1] if edge.geom_type == 'LineString' else edge.geoms[-1].coords[-1])
        L = ea.distance(eb)
        u = ((eb.x - ea.x) / L, (eb.y - ea.y) / L)
        n = (u[1], -u[0])
        if O.contains(Point((ea.x + eb.x) / 2 + n[0] * 0.5, (ea.y + eb.y) / 2 + n[1] * 0.5)):
            n = (-n[0], -n[1])
        rot = math.atan2(u[1], u[0])
        mx, my = (ea.x + eb.x) / 2, (ea.y + eb.y) / 2
        mb.box(mx - n[0] * 1.5, my - n[1] * 1.5, -0.6, L - 0.4, 3.0, 4.0, 'Ramp dark', rot=rot)
        mb.box(mx - n[0] * 0.2, my - n[1] * 0.2, 3.4, L, 0.5, GROUND - 0.45 - 3.4, 'Stone dark', rot=rot)
        for e in (-L / 2 + 0.25, L / 2 - 0.25):
            mb.box(mx + u[0] * e - n[0] * 0.2, my + u[1] * e - n[1] * 0.2, 0.0, 0.5, 0.5, 3.4, 'Stone dark', rot=rot)
    # the corner on the crossing (renders 4, 6): an L-shaped canopy over the corner shop's doors -
    # dark beams, timber slats across them, two lamps in it at night
    cs = Point(sheet_to_site(19.7, 19.3))
    cpts = list(O.exterior.coords)[:-1]
    ci = min(range(len(cpts)), key=lambda i: Point(cpts[i]).distance(cs))
    if Point(cpts[ci]).distance(cs) < 5.0:
        c0 = cpts[ci]
        for nb in (cpts[ci - 1], cpts[(ci + 1) % len(cpts)]):
            L = min(8.0, math.dist(c0, nb))
            u = ((nb[0] - c0[0]) / math.dist(c0, nb), (nb[1] - c0[1]) / math.dist(c0, nb))
            n = (u[1], -u[0])
            if O.contains(Point(c0[0] + u[0] * 1 + n[0] * 0.5, c0[1] + u[1] * 1 + n[1] * 0.5)):
                n = (-n[0], -n[1])
            rot = math.atan2(u[1], u[0])
            zc = GROUND - 1.35
            for off in (0.35, 2.5):
                q = (c0[0] + u[0] * L / 2 + n[0] * off, c0[1] + u[1] * L / 2 + n[1] * off)
                mb.box(q[0], q[1], zc, L + (2.6 if off > 1 else 0.0), 0.22, 0.32, 'Frame dark', rot=rot)
            for k3 in range(int(L / 0.32)):
                q = (c0[0] + u[0] * (0.2 + k3 * 0.32) + n[0] * 1.45, c0[1] + u[1] * (0.2 + k3 * 0.32) + n[1] * 1.45)
                mb.box(q[0], q[1], zc + 0.32, 0.07, 2.3, 0.1, 'Wood', rot=rot)
            q = (c0[0] + u[0] * L * 0.6 + n[0] * 1.45, c0[1] + u[1] * L * 0.6 + n[1] * 1.45)
            mb.box(q[0], q[1], zc - 0.03, 0.3, 0.3, 0.03, 'Night white', rot=rot)
    # the doors from the courtyard: dark glass doors in a frame, a white canopy over them
    for (dx, dy), (ox, oy) in DOORS:
        c0 = sheet_to_site(dx, dy)
        o = sheet_to_site(ox, oy)
        rot = math.atan2(o[1], o[0]) + math.pi / 2
        mb.box(c0[0] + o[0] * 0.05, c0[1] + o[1] * 0.05, 0.0, 2.6, 0.2, 3.0, 'Frame dark', rot=rot)
        mb.box(c0[0] + o[0] * 0.17, c0[1] + o[1] * 0.17, 0.05, 2.4, 0.05, 2.85, 'Glass dark', rot=rot)
        mb.box(c0[0] + o[0] * 1.0, c0[1] + o[1] * 1.0, 3.3, 3.4, 2.0, 0.25, 'White band', rot=rot)
        mb.box(c0[0] + o[0] * 1.95, c0[1] + o[1] * 1.95, 3.25, 3.4, 0.08, 0.05, 'Night white', rot=rot)
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
