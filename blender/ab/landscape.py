"""Landscape to the developer's notes on the genplan photos (21.10.2026):

  - the big school north of the plot, where «МАКТАБ» is written in blue marker: a school the size of
    that writing (117 x 24 m on the genplan), a four-storey main block along the plot with a gym and an
    assembly hall behind it, its grounds (yard, running track, pitch, courts) further north;
  - a mini-football pitch (six a side, not a full-size one) at №14, fenced, lit, with trees round it;
  - the playgrounds full of play equipment, so that they read as playgrounds at a glance;
  - the kindergarten to the genplan's shape (three wings round a stepped entrance), three storeys;
  - shrubs and flower beds on the lawns.

All in site metres, spread like the rest of the genplan (config.SPREAD). Builders add to a
MeshBuilder; they return what the caller needs to keep trees and people off them.
"""
import math

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from .config import SPREAD


# What the walk on the ground (src/sitewalk.js) must not pass through, filled by the builders:
# solids: outlines (buildings, play equipment, benches...), lines: [width, points] (fences),
# posts: [x, y, r] (masts, columns), surf: [kind, polygon] (the ground the walker stands on)
WALK = dict(solids=[], lines=[], posts=[], surf=[])


# the lamps' heads, for the site at night (src/night.js): [x, y, z, aim x, aim y, kind]; kind 0 a
# path lamp shining down, 1 a street lamp on its arm, 2 a floodlight aimed at the pitch
LIGHTS = []


def walk_reset():
    for v in WALK.values():
        v.clear()
    LIGHTS.clear()


def parts(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == 'Polygon':
        return [g]
    return [q for q in getattr(g, 'geoms', []) if q.geom_type == 'Polygon']


# ----------------------------------------------------------------------------
# small shapes
# ----------------------------------------------------------------------------

def cyl(mb, x, y, z0, z1, r, mat, n=10, top=True):
    """upright cylinder (posts, poles, mushrooms)"""
    pts = [(x + r * math.cos(2 * math.pi * k / n), y + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    mb.prism(Polygon(pts), z0, z1, mat, mat if top else None)


def disc(mb, x, y, z, r, mat, n=24):
    pts = [(x + r * math.cos(2 * math.pi * k / n), y + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    mb.polygon_face(Polygon(pts), z, mat)


def bar(mb, a, b, za, zb, w, mat):
    """a straight member from (a, za) to (b, zb), square section w (rails, chains, struts)"""
    mb.tube([a, b], [za - w / 2, zb - w / 2], [za + w / 2, zb + w / 2], w, mat)


def gable(mb, cx, cy, z, sx, sy, rise, mat, rot=0.0):
    """a small pitched roof: ridge along local x, eaves at z, ridge at z + rise"""
    c, s = math.cos(rot), math.sin(rot)
    P = lambda x, y, zz: (cx + c * x - s * y, cy + s * x + c * y, zz)
    hx, hy = sx / 2, sy / 2
    a, b = P(-hx, -hy, z), P(hx, -hy, z)
    cc, d = P(hx, hy, z), P(-hx, hy, z)
    r0, r1 = P(-hx, 0, z + rise), P(hx, 0, z + rise)
    for f in ([a, b, r1, r0], [cc, d, r0, r1], [a, r0, d], [b, cc, r1]):
        mb.face(f, mat)
        mb.face(f[::-1], mat)


class Frame:
    """local frame: origin, axis u (radians from east), v to the left of u"""

    def __init__(self, x, y, ang):
        self.x, self.y, self.c, self.s, self.ang = x, y, math.cos(ang), math.sin(ang), ang

    def __call__(self, u, v):
        return (self.x + self.c * u - self.s * v, self.y + self.s * u + self.c * v)

    def rect(self, u0, v0, u1, v1):
        return Polygon([self(u0, v0), self(u1, v0), self(u1, v1), self(u0, v1)])

    def box(self, mb, u, v, z0, su, sv, sz, mat, top=True):
        x, y = self(u, v)
        mb.box(x, y, z0, su, sv, sz, mat, rot=self.ang, top=top)


# ----------------------------------------------------------------------------
# facades
# ----------------------------------------------------------------------------

def window_row(mb, a, b, z0, floors, fh, bay, win_w, win_h, sill, glass, frame, fin=None, fin_every=1, out=0.0):
    """Windows along a wall from a to b (the wall's outside to the right of a->b, as for a CCW
    ring), one per bay on each floor, recessed glass in a frame; optional coloured fins between
    bays (a list of materials cycled bay by bay)."""
    L = math.dist(a, b)
    if L < bay * 0.8:
        return
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    nx, ny = uy, -ux
    rot = math.atan2(uy, ux)
    n = max(1, int(L // bay))
    off = (L - n * bay) / 2
    for f in range(floors):
        zz = z0 + f * fh + sill
        for k in range(n):
            s = off + (k + 0.5) * bay
            c = (a[0] + ux * s + nx * (0.03 + out), a[1] + uy * s + ny * (0.03 + out))
            mb.box(c[0], c[1], zz - 0.06, win_w + 0.12, 0.08, win_h + 0.12, frame, rot=rot)
            mb.box(c[0] + nx * 0.03, c[1] + ny * 0.03, zz, win_w, 0.06, win_h, glass, rot=rot)
    if fin:
        for k in range(n + 1):
            if k % fin_every:
                continue
            s = off + k * bay
            c = (a[0] + ux * s + nx * 0.18, a[1] + uy * s + ny * 0.18)
            mb.box(c[0], c[1], z0 + 0.6, 0.32, 0.36, floors * fh - 0.6, fin[k % len(fin)], rot=rot)


def ring_edges(poly):
    cs = list(poly.exterior.coords)[:-1]
    if not poly.exterior.is_ccw:
        cs = cs[::-1]
    return list(zip(cs, cs[1:] + cs[:1]))


def block(mb, poly, z0, z1, wall, parapet='Stone white', roof='Roof', coping=0.9):
    """a flat-roofed volume: walls, roof, a parapet with a coping"""
    mb.prism(poly, z0, z1, wall)
    mb.polygon_face(poly.buffer(-0.35, join_style='mitre'), z1 + 0.04, roof)
    ring = poly.buffer(0.08, join_style='mitre').difference(poly.buffer(-0.35, join_style='mitre'))
    mb.prism(ring, z1, z1 + coping, parapet, parapet)


# ----------------------------------------------------------------------------
# the school
# ----------------------------------------------------------------------------

# where «МАКТАБ» is written on the genplan photo (tools/ab: photo -> site homography on the five
# blocks and the hospital, 1-2 m), genplan metres: the letters' rectangle
MAKTAB = [(-116.1, 38.2), (-2.7, 66.6), (-8.5, 90.0), (-122.0, 61.7)]


def bench(mb, x, y, z, rot):
    ca, sa = math.cos(rot), math.sin(rot)
    WALK['solids'].append(affinity.rotate(box(x - 0.95, y - 0.3, x + 0.95, y + 0.3), rot, origin=(x, y), use_radians=True))
    mb.box(x, y, z + 0.42, 1.8, 0.45, 0.06, 'Wood', rot=rot)
    mb.box(x - sa * 0.22, y + ca * 0.22, z + 0.48, 1.8, 0.06, 0.42, 'Wood', rot=rot)
    for e in (-0.75, 0.75):
        mb.box(x + ca * e, y + sa * e, z, 0.08, 0.45, 0.42, 'Lamp dark', rot=rot)


def school_frame(plot):
    """The school's frame: u along the writing (west to east), v away from the plot; the main
    block's front 5 m off the plot's edge. Returns (frame, length, depth of the writing)."""
    S = SPREAD
    R = [(x * S, y * S) for x, y in MAKTAB]
    L = math.dist(R[0], R[1])
    W = math.dist(R[1], R[2])
    ang = math.atan2(R[1][1] - R[0][1], R[1][0] - R[0][0])
    cx = sum(p[0] for p in R) / 4
    cy = sum(p[1] for p in R) / 4
    F = Frame(cx, cy, ang)
    d = plot.distance(F.rect(-L / 2, -W / 2, L / 2, -W / 2 + 0.1))
    shift = 5.0 - d
    return Frame(cx - F.s * shift, cy + F.c * shift, ang), L, W


# the school's ground along v (away from the plot), from the plot's side: a green strip by the
# fence, the sports ground, the yard, the school, a green strip at the back (21.10.2026: the user
# asked for the stadium first and the school behind it)
DEPTH = 131.5


def school_grounds(plot):
    """the school's fenced ground (for clearing the genplan's surfaces off it before they are drawn)"""
    F, L, W = school_frame(plot)
    return F.rect(-L / 2 - 8.0, -W / 2 - 3.5, L / 2 + 8.0, -W / 2 - 3.5 + DEPTH)


def school(mb, labels, plot, rnd, people):
    """The school north of the plot, where the genplan photo has «МАКТАБ», as long as the writing.
    From the plot's side: the sports ground (a 200 m track round a pitch, a court at its east end, a
    path from the gate at its west end), the yard with trees and benches, then the school: the
    entrance hall facing the yard (glass, two storeys, a canopy over the steps), the four-storey main
    block (white render with terracotta, ochre and teal fins between the windows, glass stair towers)
    and behind it the gym (teal) and the assembly hall (terracotta). All fenced, trees along the
    fence. Returns (the ground, its trees)."""
    F, L, W = school_frame(plot)
    ang = F.ang
    H, fh = 15.2, 3.8            # four storeys
    vf = -W / 2 - 3.5            # the fence on the plot's side
    vt = vf + 33.5               # the track's middle
    vy0, vy1 = vf + 61.5, vf + 79.5   # the yard
    vs = vy1                     # the entrance hall's front
    v0, v1 = vs + 7.0, vs + 24.0      # the main block
    main = F.rect(-L / 2, v0, L / 2, v1)
    lobby = F.rect(-15.0, vs, 15.0, v0)
    gym = F.rect(-L / 2 + 2.0, v1, -L / 2 + 34.0, v1 + 24.0)
    hall = F.rect(L / 2 - 30.0, v1, L / 2 - 2.0, v1 + 20.0)
    # main block
    mb.prism(main.buffer(0.04, join_style='mitre'), 0.0, 0.7, 'School plinth')
    block(mb, main, 0.0, H, 'School render', 'School render')
    fins = ['School terracotta', 'School ochre', 'School terracotta', 'School teal']
    for a, b in ring_edges(main):
        Le = math.dist(a, b)
        if Le > 40:
            window_row(mb, a, b, 0.0, 4, fh, 3.3, 2.5, 2.1, 0.95, 'Window glass', 'Frame dark', fin=fins)
            ux, uy = (b[0] - a[0]) / Le, (b[1] - a[1]) / Le
            nx, ny = uy, -ux
            for f in range(1, 4):
                q0 = (a[0] + nx * 0.06, a[1] + ny * 0.06)
                q1 = (b[0] + nx * 0.06, b[1] + ny * 0.06)
                mb.tube([q0, q1], [f * fh - 0.18] * 2, [f * fh + 0.12] * 2, 0.16, 'School render')
        else:
            window_row(mb, a, b, 0.0, 4, fh, 3.3, 1.6, 2.1, 0.95, 'Window glass', 'Frame dark')
    # glass stair towers at the thirds of the front (on the yard), a little proud of it
    for u in (-L / 3, L / 3):
        core = F.rect(u - 3.2, v0 - 0.6, u + 3.2, v0 + 0.2)
        mb.prism(core, 0.0, H + 1.2, 'Stair glass', 'Frame dark')
        for z in np.arange(fh, H + 0.1, fh):
            mb.prism(core.buffer(0.05, join_style='mitre'), z - 0.12, z + 0.12, 'Frame dark', 'Frame dark')
        for k in (-3.15, 0.0, 3.15):
            x, y = F(u + k, v0 - 0.62)
            mb.box(x, y, 0.0, 0.14, 0.14, H + 1.2, 'Frame dark', rot=ang)
    # gym and assembly hall behind it
    for g, h, wall in ((gym, 10.5, 'School teal'), (hall, 9.0, 'School terracotta')):
        mb.prism(g.buffer(0.04, join_style='mitre'), 0.0, 0.7, 'School plinth')
        block(mb, g, 0.0, h, wall, 'School render')
        for a, b in ring_edges(g):
            if math.dist(a, b) > 12 and LineString([a, b]).distance(main) > 1.0:
                window_row(mb, a, b, h - 3.4, 1, 3.0, 3.0, 2.4, 1.7, 0.0, 'Window glass', 'Frame light')
    # entrance hall: two storeys of glass in front of the main block, a canopy over the steps
    block(mb, lobby, 0.0, 8.4, 'Window glass', 'School render', coping=0.6)
    for a, b in ring_edges(lobby):
        Le = math.dist(a, b)
        ux, uy = (b[0] - a[0]) / Le, (b[1] - a[1]) / Le
        nx, ny = uy, -ux
        n = max(1, int(Le / 1.8))
        for k in range(n + 1):
            sx = Le * k / n
            x, y = a[0] + ux * sx + nx * 0.05, a[1] + uy * sx + ny * 0.05
            mb.box(x, y, 0.0, 0.1, 0.1, 8.4, 'Frame dark', rot=math.atan2(uy, ux))
        for z in (0.05, 4.2, 8.3):
            mb.tube([(a[0] + nx * 0.05, a[1] + ny * 0.05), (b[0] + nx * 0.05, b[1] + ny * 0.05)], [z - 0.06] * 2, [z + 0.06] * 2, 0.12, 'Frame dark')
    canopy = F.rect(-11.0, vs - 4.5, 11.0, vs)
    mb.prism(canopy, 4.0, 4.35, 'School render', 'School render', 'School render')
    for u in (-10.2, -3.4, 3.4, 10.2):
        x, y = F(u, vs - 3.9)
        cyl(mb, x, y, 0.1, 4.0, 0.14, 'Frame dark')
    for k in range(3):
        mb.prism(F.rect(-8.0, vs - 0.9 * (3 - k), 8.0, vs), 0.1, 0.1 + 0.15 * (k + 1), 'Stone white', 'Stone white')
    # solar panels on the main roof
    for k in range(-5, 6):
        x, y = F(k * 10.0, v0 + 8.5)
        if abs(k * 10.0) < L / 2 - 5:
            mb.box(x, y, H + 0.4, 7.5, 9.0, 0.08, 'Solar panel', rot=ang)

    # ---- the ground ----
    built = unary_union([main, gym, hall, lobby])
    WALK['solids'].extend([main.buffer(0.7, join_style='mitre'), gym, hall, lobby.buffer(0.1, join_style='mitre')])
    for u in (-L / 3, L / 3):
        WALK['solids'].append(F.rect(u - 3.3, v0 - 0.7, u + 3.3, v0 + 0.2))
    for u in (-10.2, -3.4, 3.4, 10.2):
        x, y = F(u, vs - 3.9)
        WALK['posts'].append([x, y, 0.15])
    ground = F.rect(-L / 2 - 8.0, vf, L / 2 + 8.0, vf + DEPTH)
    mb.polygon_face(ground.difference(built.buffer(0.02)), 0.05, 'Lawn')
    yard = F.rect(-L / 2 - 8.0, vy0, L / 2 + 8.0, vy1 + 0.0).union(F.rect(-L / 2 - 8.0, vy1, L / 2 + 8.0, v0)).difference(built.buffer(0.02))
    mb.polygon_face(yard, 0.1, 'Paving')
    # the path from the gate on the plot's side, past the west end of the track, to the yard
    gate = Point(F(-L / 2 - 1.0, vf))
    path = F.rect(-L / 2 - 3.5, vf, -L / 2 + 1.5, vy0 + 0.5)
    mb.polygon_face(path, 0.1, 'Paving')
    WALK['surf'] += [['school_lawn', ground], ['school_paving', unary_union([yard, path])]]
    # the sports ground: a 200 m track round a pitch, a court at its east end
    def stadium(half_len, r):
        return unary_union([F.rect(-half_len, vt - r, half_len, vt + r),
                            Point(F(-half_len, vt)).buffer(r, 48), Point(F(half_len, vt)).buffer(r, 48)])
    track_outer, track_inner = stadium(28.0, 26.0), stadium(28.0, 19.5)
    mb.polygon_face(track_outer.difference(track_inner), 0.08, 'Track red')
    mb.polygon_face(track_inner, 0.08, 'Turf')
    for k in range(1, 4):
        ln = track_inner.buffer(1.6 * k).exterior
        c2 = list(ln.coords)[:-1]
        mb.tube(c2, [0.085] * len(c2), [0.095] * len(c2), 0.06, 'Road line', closed=True)
    pitch_lines(mb, F, 0.0, vt, 52.0, 32.0, 0.085, goals=True)
    WALK['surf'] += [['track', track_outer.difference(track_inner)], ['pitch', track_inner]]
    cu0, cu1 = 57.0, min(L / 2 + 7.0, 72.0)
    court = F.rect(cu0, vt - 14.0, cu1, vt + 14.0)
    if not court.intersects(track_outer.buffer(1.5)):
        mb.polygon_face(court, 0.08, 'School teal')
        mb.polygon_face(court.buffer(-1.0), 0.1, 'Court blue')
        cm = (cu0 + cu1) / 2
        WALK['surf'].append(['track', court])
        for sv in (-1, 1):
            x, y = F(cm, vt + sv * 13.0)
            WALK['posts'].append([x, y, 0.12])
            cyl(mb, x, y, 0.08, 3.05, 0.06, 'Metal', n=8)
            F.box(mb, cm, vt + sv * 12.55, 2.9, 1.8, 0.05, 1.05, 'Frame light')
    # the fence, the gate on the plot's side
    cs = list(ground.exterior.coords)
    for a, b in zip(cs, cs[1:]):
        seg = LineString([a, b])
        cut = seg.difference(gate.buffer(2.5)) if seg.distance(gate) < 0.5 else seg
        for p in getattr(cut, 'geoms', [cut]):
            if p.is_empty or p.length < 0.5:
                continue
            c2 = list(p.coords)
            WALK['lines'].append([0.08, c2])
            mb.ribbon(c2, 0.08, 1.9, 'Pitch fence', double=True)
            mb.tube(c2, [1.86] * len(c2), [1.92] * len(c2), 0.05, 'Fence')
            for q in [p.interpolate(t) for t in np.arange(0.0, p.length + 0.01, 2.5)]:
                mb.box(q.x, q.y, 0.05, 0.06, 0.06, 1.95, 'Fence')
    # trees: a row along the fence, a row with benches in the yard
    trees = []
    c0 = ground.centroid
    for t in np.arange(4.0, ground.exterior.length, 8.0):
        q = ground.exterior.interpolate(t)
        k = 2.2 / max(1.0, q.distance(c0))
        x, y = q.x + (c0.x - q.x) * k, q.y + (c0.y - q.y) * k
        pt = Point(x, y)
        if pt.distance(built) < 4.5 or pt.distance(track_outer) < 2.5 or pt.distance(gate) < 5 or pt.distance(path) < 1.5 or pt.distance(court) < 1.5:
            continue
        trees.append([round(x, 2), round(y, 2), 0.05, round(rnd.uniform(7.5, 11.0), 2), round(rnd.uniform(2.6, 3.6), 2), 'broad'])
    for u in np.arange(-L / 2 + 14.0, L / 2 - 13.0, 12.0):
        x, y = F(u, (vy0 + vy1) / 2 - 2.0)
        trees.append([round(x, 2), round(y, 2), 0.1, round(rnd.uniform(6.5, 8.5), 2), round(rnd.uniform(2.3, 3.0), 2), 'broad'])
        bx, by = F(u + 4.0, (vy0 + vy1) / 2 - 0.5)
        bench(mb, bx, by, 0.1, ang + math.pi)
    for k in range(16):
        x, y = F(rnd.uniform(-L / 2, L / 2), rnd.uniform(vy0 + 2.0, vy1 - 1.0))
        people.append([round(x, 2), round(y, 2), 0.1, rnd.randrange(6)])
    for k in range(12):
        x, y = F(rnd.uniform(-30, 30), rnd.uniform(vt - 12, vt + 12))
        people.append([round(x, 2), round(y, 2), 0.08, rnd.randrange(6)])
    c = main.centroid
    labels.append(dict(x=round(c.x, 2), y=round(c.y, 2), z=H + 5, ru='Школа', tj='Мактаб', kind='school'))
    return ground, trees


def pitch_lines(mb, F, uc, vc, Lp, Wp, z, goals=False, circle=None, area=None, goal_w=None):
    """White lines of a football pitch (local frame F, centre uc, vc, length Lp along u)"""
    lw = 0.08
    def line(p, q):
        mb.tube([F(*p), F(*q)], [z] * 2, [z + 0.012] * 2, lw, 'Road line')
    hu, hv = Lp / 2, Wp / 2
    for p, q in (((-hu, -hv), (hu, -hv)), ((-hu, hv), (hu, hv)), ((-hu, -hv), (-hu, hv)), ((hu, -hv), (hu, hv)), ((0, -hv), (0, hv))):
        line((uc + p[0], vc + p[1]), (uc + q[0], vc + q[1]))
    r = circle or min(9.15, Wp * 0.2)
    pts = [F(uc + r * math.cos(t), vc + r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 40, endpoint=False)]
    mb.tube(pts, [z] * 40, [z + 0.012] * 40, lw, 'Road line', closed=True)
    spot = [F(uc + 0.15 * math.cos(t), vc + 0.15 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 10, endpoint=False)]
    mb.polygon_face(Polygon(spot), z + 0.013, 'Road line')
    ad, aw = area or (min(16.5, Lp * 0.16), min(40.3, Wp * 0.6))
    gw = goal_w or min(7.32, Wp * 0.2)
    for sgn in (-1, 1):
        x0 = uc + sgn * hu
        x1 = x0 - sgn * ad
        line((x0, vc - aw / 2), (x1, vc - aw / 2))
        line((x1, vc - aw / 2), (x1, vc + aw / 2))
        line((x1, vc + aw / 2), (x0, vc + aw / 2))
        if goals:
            goal(mb, F, x0, vc, sgn, gw, min(2.44, gw * 0.4), z)


def goal(mb, F, u, v, sgn, w, h, z, depth=None):
    """a goal on the line at (u, v), its net behind it (sgn: which end, +1 the far end)"""
    d = depth or max(0.9, h * 0.5)
    t = 0.09
    for k in (-w / 2, w / 2):
        x, y = F(u, v + k)
        cyl(mb, x, y, z, z + h, t / 2, 'Goal white', n=8)
        xb, yb = F(u + sgn * d, v + k)
        cyl(mb, xb, yb, z, z + h * 0.55, 0.03, 'Goal white', n=6)
        bar(mb, F(u, v + k), F(u + sgn * d, v + k), z + h, z + h * 0.55, 0.05, 'Goal white')
    bar(mb, F(u, v - w / 2), F(u, v + w / 2), z + h, z + h, t, 'Goal white')
    bar(mb, F(u + sgn * d, v - w / 2), F(u + sgn * d, v + w / 2), z + h * 0.55, z + h * 0.55, 0.04, 'Goal white')
    # the net: back, roof, sides
    a, b = F(u + sgn * d, v - w / 2), F(u + sgn * d, v + w / 2)
    mb.quad_wall(a, b, z, z + h * 0.55, 'Net')
    mb.quad_wall(a, b, z, z + h * 0.55, 'Net', flip=True)
    for f in ([(*F(u, v - w / 2), z + h), (*F(u, v + w / 2), z + h), (*F(u + sgn * d, v + w / 2), z + h * 0.55), (*F(u + sgn * d, v - w / 2), z + h * 0.55)],):
        mb.face(f, 'Net')
        mb.face(f[::-1], 'Net')
    for k in (-w / 2, w / 2):
        f = [(*F(u, v + k), z), (*F(u + sgn * d, v + k), z), (*F(u + sgn * d, v + k), z + h * 0.55), (*F(u, v + k), z + h)]
        mb.face(f, 'Net')
        mb.face(f[::-1], 'Net')


# ----------------------------------------------------------------------------
# the mini-football pitch (№14)
# ----------------------------------------------------------------------------

def fit_pitch(sport, plot, hard, soft):
    """Where the six-a-side pitch goes: in the corner the genplan gives №14, turned as drawn (its
    long side along the road, the goals at its north-west and south-east ends - not across, as the
    user pointed out on the genplan photo), as large as a six-a-side pitch should be: 32 x 19 m down
    to the drawn 20 x 12 m of pitch, 1.5 m round it inside the fence. Never on hard (roads,
    buildings, the plot's edge); the neighbouring playground (soft) gives way, up to 250 m2 of it.
    Returns (frame, length, width, fence outline)."""
    from shapely.prepared import prep
    g = max(parts(sport), key=lambda q: q.area)
    r = g.minimum_rotated_rectangle
    cs = list(r.exterior.coords)
    e1 = (cs[1][0] - cs[0][0], cs[1][1] - cs[0][1])
    e2 = (cs[2][0] - cs[1][0], cs[2][1] - cs[1][1])
    if math.hypot(*e1) < math.hypot(*e2):
        e1, e2 = e2, e1
    ang = math.atan2(e1[1], e1[0])
    c0 = r.centroid
    room = prep(plot.buffer(-1.5).difference(hard.buffer(1.2)))
    soft_b = soft.buffer(1.2)
    for Lp, Wp in ((32, 19), (30, 18), (28, 17), (26, 16), (25, 15), (24, 15), (23, 14), (22, 13), (21, 12.5), (20.5, 12)):
        cands = []
        for du in np.arange(-16.0, 16.1, 0.5):
            for dv in np.arange(-6.0, 6.1, 0.5):
                F = Frame(c0.x + math.cos(ang) * du - math.sin(ang) * dv, c0.y + math.sin(ang) * du + math.cos(ang) * dv, ang)
                fence = F.rect(-Lp / 2 - 1.5, -Wp / 2 - 1.5, Lp / 2 + 1.5, Wp / 2 + 1.5)
                if room.contains(fence):
                    cands.append((fence.intersection(soft_b).area, abs(du) + abs(dv), F))
        if cands:
            lost, _, F = min(cands, key=lambda c: (c[0], c[1]))
            if lost <= 250.0:
                return F, float(Lp), float(Wp), F.rect(-Lp / 2 - 1.5, -Wp / 2 - 1.5, Lp / 2 + 1.5, Wp / 2 + 1.5)
    F = Frame(c0.x, c0.y, ang)
    Lp, Wp = max(18.0, math.hypot(*e1) - 3.0), max(11.0, math.hypot(*e2) - 3.0)
    return F, Lp, Wp, F.rect(-Lp / 2 - 1.5, -Wp / 2 - 1.5, Lp / 2 + 1.5, Wp / 2 + 1.5)


def mini_pitch(mb, fit, plot, keep_off, rnd, people):
    """The six-a-side pitch (fit_pitch): artificial turf mown in stripes, the lines of a
    mini-football pitch, goals with nets, a 4 m mesh fence with a gate, four floodlights, team
    benches under clear roofs, players, and trees round it. Returns its trees."""
    F, Lp, Wp, _ = fit
    ang = F.ang
    z = 0.14
    hu, hv = Lp / 2, Wp / 2
    fence = F.rect(-hu - 1.5, -hv - 1.5, hu + 1.5, hv + 1.5)
    # base and turf in stripes across the pitch
    mb.polygon_face(fence, z - 0.02, 'Turf')
    n = max(4, int(round(Lp / 3.0)))
    for k in range(n):
        u0 = -hu + Lp * k / n
        u1 = -hu + Lp * (k + 1) / n
        mb.polygon_face(F.rect(u0, -hv, u1, hv), z, 'Turf light' if k % 2 else 'Turf')
    raised_edge = fence.buffer(0.15, join_style='mitre').difference(fence)
    mb.prism(raised_edge, 0.0, z + 0.05, 'Kerb', 'Kerb')
    WALK['surf'].append(['pitch', fence])
    gw, gh = 3.0, 2.0
    pitch_lines(mb, F, 0.0, 0.0, Lp, Wp, z + 0.002, goals=True, circle=3.0, area=(min(6.0, Lp * 0.2), min(Wp - 2.0, 12.0)), goal_w=gw)
    # penalty spots at 6 m
    for sgn in (-1, 1):
        u = sgn * (hu - 6.0)
        if abs(u) > 2.0:
            pts = [F(u + 0.12 * math.cos(t), 0.12 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 10, endpoint=False)]
            mb.polygon_face(Polygon(pts), z + 0.015, 'Road line')
    # fence: 4 m of green mesh on posts, a top rail, a gate in the middle of one long side
    cs = list(fence.exterior.coords)
    gate_c = Point(F(0.0, -hv - 1.5))
    for a, b in zip(cs, cs[1:]):
        seg = LineString([a, b])
        pieces = [seg] if seg.distance(gate_c) > 0.3 else list(getattr(seg.difference(gate_c.buffer(0.7)), 'geoms', [seg.difference(gate_c.buffer(0.7))]))
        for p in pieces:
            if p.is_empty or p.length < 0.3:
                continue
            c2 = list(p.coords)
            WALK['lines'].append([0.1, c2])
            mb.ribbon(c2, z, z + 4.0, 'Pitch fence', double=True)
            mb.tube(c2, [z + 3.95] * len(c2), [z + 4.05] * len(c2), 0.06, 'Fence')
            mb.tube(c2, [z + 0.95] * len(c2), [z + 1.02] * len(c2), 0.05, 'Fence')
            for q in [p.interpolate(t) for t in np.arange(0.0, p.length + 0.01, 2.5)]:
                cyl(mb, q.x, q.y, 0.0, z + 4.1, 0.045, 'Fence', n=6)
    for k in (-0.7, 0.7):
        x, y = F(k, -hv - 1.5)
        cyl(mb, x, y, 0.0, z + 2.3, 0.05, 'Fence', n=6)
    # floodlights: four masts outside the corners, two lamps each, aimed at the pitch
    for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x, y = F(su * (hu + 2.3), sv * (hv + 2.3))
        WALK['posts'].append([x, y, 0.12])
        cyl(mb, x, y, 0.0, 9.0, 0.09, 'Lamp dark', n=8)
        a2 = math.atan2(-(y - F(0, 0)[1]), -(x - F(0, 0)[0]))
        for k in (-0.35, 0.35):
            hx, hy = x + math.cos(a2) * 0.5 - math.sin(a2) * k, y + math.sin(a2) * 0.5 + math.cos(a2) * k
            mb.box(hx, hy, 8.65, 0.55, 0.5, 0.32, 'Lamp dark', rot=a2)
            mb.box(hx + math.cos(a2) * 0.28, hy + math.sin(a2) * 0.28, 8.68, 0.04, 0.42, 0.26, 'Lamp glow', rot=a2)
            LIGHTS.append([round(hx + math.cos(a2) * 0.3, 2), round(hy + math.sin(a2) * 0.3, 2), 8.68,
                           round(F(0, 0)[0], 2), round(F(0, 0)[1], 2), 2])
        bar(mb, (x, y), (x + math.cos(a2) * 0.5, y + math.sin(a2) * 0.5), 8.8, 8.8, 0.08, 'Lamp dark')
    # team benches under clear roofs on the long side away from the gate
    for su in (-1, 1):
        u = su * min(6.5, hu * 0.4)
        x, y = F(u, hv + 0.6)
        F2 = Frame(x, y, ang)
        WALK['solids'].append(F2.rect(-1.95, -0.6, 1.95, 0.5))
        F2.box(mb, 0.0, 0.0, 0.0, 3.6, 0.45, 0.45, 'Wood')
        F2.box(mb, 0.0, 0.25, 0.45, 3.6, 0.06, 0.4, 'Wood')
        for e in (-1.7, 1.7):
            F2.box(mb, e, 0.1, 0.0, 0.06, 0.06, 2.3, 'Lamp dark')
        p = [F2(-1.9, -0.6), F2(1.9, -0.6), F2(1.9, 0.5), F2(-1.9, 0.5)]
        mb.face([(*p[0], 2.1), (*p[1], 2.1), (*p[2], 2.3), (*p[3], 2.3)], 'Shop glass')
        mb.face([(*p[3], 2.3), (*p[2], 2.3), (*p[1], 2.1), (*p[0], 2.1)], 'Shop glass')
    # players
    for k in range(10):
        u, v = rnd.uniform(-hu + 2, hu - 2), rnd.uniform(-hv + 1.5, hv - 1.5)
        x, y = F(u, v)
        people.append([round(x, 2), round(y, 2), z, rnd.randrange(6)])
    # trees round it, outside the floodlights
    trees = []
    ring = fence.buffer(7.0, join_style='mitre').exterior
    for t in np.arange(3.0, ring.length, 8.0):
        q = ring.interpolate(t)
        if not plot.buffer(-2.0).contains(q) or keep_off.buffer(2.0).contains(q):
            continue
        trees.append([round(q.x, 2), round(q.y, 2), 0.15, round(rnd.uniform(6.0, 8.0), 2), round(rnd.uniform(2.0, 2.6), 2), 'broad'])
    return trees


# ----------------------------------------------------------------------------
# playgrounds
# ----------------------------------------------------------------------------

PLAY = ['Kinder red', 'Kinder yellow', 'Kinder blue', 'Kinder green', 'Play orange']


def play_tower(mb, F, rnd, col):
    """two towers with roofs, a bridge between them, a tube slide, a straight slide, a climbing
    wall and a ladder: the big piece of a playground (about 7 x 4 m)"""
    for (u, v, h) in ((-1.6, 0.0, 1.2), (1.8, 0.4, 1.5)):
        for du, dv in ((-0.75, -0.75), (0.75, -0.75), (0.75, 0.75), (-0.75, 0.75)):
            x, y = F(u + du, v + dv)
            mb.box(x, y, 0.0, 0.12, 0.12, h + 1.9, 'Play blue', rot=F.ang)
        F.box(mb, u, v, h, 1.62, 1.62, 0.1, 'Wood')
        for dv in (-0.78, 0.78):
            F.box(mb, u, v + dv, h + 0.1, 1.5, 0.05, 0.7, col[0])
        x, y = F(u, v)
        gable(mb, x, y, h + 1.85, 1.9, 1.9, 0.75, col[1], rot=F.ang)
    # bridge
    a, b = F(-0.85, 0.1), F(1.05, 0.35)
    bar(mb, a, b, 1.2, 1.5, 0.75, 'Wood')
    for dv in (-0.36, 0.36):
        bar(mb, F(-0.85, 0.1 + dv), F(1.05, 0.35 + dv), 1.9, 2.2, 0.04, 'Metal')
    # straight slide off tower 1
    s0, s1 = F(-2.4, 0.0), F(-5.0, 0.0)
    mb.tube([s0, s1], [1.15, 0.25], [1.2, 0.3], 0.62, col[2])
    for dv in (-0.33, 0.33):
        bar(mb, F(-2.4, dv), F(-5.0, dv), 1.4, 0.45, 0.05, col[2])
    # tube slide off tower 2: a spiral of segments
    pts, zs = [], []
    for k in range(13):
        t = k / 12
        a2 = t * math.pi * 1.25
        pts.append(F(2.6 + 1.25 * math.sin(a2), 0.4 + 1.25 * (1 - math.cos(a2))))
        zs.append(1.45 - 1.15 * t)
    mb.tube(pts, [z - 0.32 for z in zs], [z + 0.32 for z in zs], 0.75, col[3])
    # climbing wall with holds, ladder
    a, b = F(1.0, -0.4), F(2.6, -0.4)
    w0 = [(*F(1.0, -0.35), 0.0), (*F(2.6, -0.35), 0.0), (*F(2.6, -1.25), 1.5), (*F(1.0, -1.25), 1.5)]
    for f in (w0, w0[::-1]):
        mb.face(f, col[4])
    for k in range(9):
        t, s = rnd.random(), rnd.random()
        x, y = F(1.1 + 1.4 * t, -0.4 - 0.85 * s)
        mb.box(x, y, 1.5 * s + 0.05, 0.12, 0.12, 0.09, PLAY[k % len(PLAY)])
    for k in range(5):
        F.box(mb, -1.6, -1.05 - 0.12 * k, 0.25 * k + 0.2, 0.7, 0.12, 0.05, 'Metal')


def swings(mb, F, col, nest=False):
    for e in (-1.6, 1.6):
        for dv in (-0.7, 0.7):
            bar(mb, F(e, dv), F(e, 0.0), 0.0, 2.4, 0.09, col)
    bar(mb, F(-1.6, 0.0), F(1.6, 0.0), 2.4, 2.4, 0.11, col)
    if nest:
        x, y = F(0.0, 0.0)
        disc(mb, x, y, 0.55, 0.55, 'Kinder red', n=20)
        for k in range(4):
            a2 = k * math.pi / 2
            bar(mb, (x + 0.45 * math.cos(a2), y + 0.45 * math.sin(a2)), (x, y), 0.55, 2.35, 0.02, 'Metal')
    else:
        for e in (-0.7, 0.7):
            F.box(mb, e, 0.0, 0.45, 0.48, 0.2, 0.05, 'Rubber blue')
            for d in (-0.2, 0.2):
                bar(mb, F(e + d, 0.0), F(e + d, 0.0), 0.5, 2.35, 0.02, 'Metal')


def carousel(mb, F, col):
    x, y = F(0.0, 0.0)
    cyl(mb, x, y, 0.0, 0.32, 0.12, 'Metal', n=8)
    cyl(mb, x, y, 0.28, 0.36, 1.0, col, n=24)
    cyl(mb, x, y, 0.36, 1.05, 0.05, 'Metal', n=6)
    ring = [(x + 0.75 * math.cos(t), y + 0.75 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 18, endpoint=False)]
    mb.tube(ring, [0.95] * 18, [1.0] * 18, 0.05, 'Metal', closed=True)
    for k in range(4):
        a2 = k * math.pi / 2
        bar(mb, (x + 0.75 * math.cos(a2), y + 0.75 * math.sin(a2)), (x, y), 0.36, 0.98, 0.04, 'Metal')


def seesaw(mb, F, col):
    F.box(mb, 0.0, 0.0, 0.0, 0.3, 0.3, 0.45, 'Metal')
    a, b = F(-1.6, 0.0), F(1.6, 0.0)
    bar(mb, a, b, 0.3, 0.75, 0.22, col)
    for e, z in ((-1.3, 0.62), (1.3, 0.98)):
        x, y = F(e, 0.0)
        bar(mb, F(e, -0.18), F(e, 0.18), z, z, 0.05, 'Metal')


def spring(mb, F, col, rnd):
    x, y = F(0.0, 0.0)
    cyl(mb, x, y, 0.0, 0.35, 0.1, 'Metal', n=8)
    mb.blob(x, y, 0.62, 0.42, 0.18, 0.28, col, subdiv=1)
    mb.blob(*F(0.32, 0.0), 0.92, 0.16, 0.14, 0.16, col, subdiv=1)


def sandbox(mb, F, rnd):
    box_ = F.rect(-1.6, -1.6, 1.6, 1.6)
    mb.prism(box_.difference(box_.buffer(-0.12, join_style='mitre')), 0.0, 0.32, 'Wood', 'Wood')
    mb.polygon_face(box_.buffer(-0.12, join_style='mitre'), 0.2, 'Sand')
    for su, sv in ((-1.5, -1.5), (1.5, -1.5), (1.5, 1.5), (-1.5, 1.5)):
        x, y = F(su, sv)
        cyl(mb, x, y, 0.0, 2.3, 0.05, 'Wood', n=6)
    x, y = F(0.0, 0.0)
    gable(mb, x, y, 2.3, 3.4, 3.4, 0.5, 'Canopy', rot=F.ang)
    for k in range(3):
        mb.blob(*F(rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8)), 0.24, 0.3, 0.25, 0.08, 'Sand', subdiv=1)


def playhouse(mb, F, col):
    hut = F.rect(-0.9, -0.8, 0.9, 0.8)
    walls = hut.difference(hut.buffer(-0.06, join_style='mitre')).difference(F.rect(-0.35, -0.9, 0.35, -0.6))
    mb.prism(walls, 0.0, 1.35, col[0], col[0])
    x, y = F(0.0, 0.0)
    gable(mb, x, y, 1.35, 2.1, 1.9, 0.7, col[1], rot=F.ang)
    F.box(mb, 0.0, 0.0, 0.0, 1.7, 1.5, 0.05, 'Wood')


def climber(mb, F, col):
    """a rope pyramid: a mast and ropes to a ring of anchors"""
    x, y = F(0.0, 0.0)
    cyl(mb, x, y, 0.0, 3.2, 0.06, 'Metal', n=8)
    for k in range(8):
        a2 = k * math.pi / 4
        p = (x + 1.8 * math.cos(a2), y + 1.8 * math.sin(a2))
        bar(mb, p, (x, y), 0.05, 3.1, 0.035, col)
        cyl(mb, p[0], p[1], 0.0, 0.12, 0.08, 'Metal', n=6)
    for r, z in ((1.25, 0.9), (0.75, 1.8)):
        ring = [(x + r * math.cos(t), y + r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
        mb.tube(ring, [z] * 16, [z + 0.035] * 16, 0.035, col, closed=True)


ITEMS = [
    # name, footprint (u, v) with its safety zone, minimum area of the play area
    ('tower', (9.0, 6.0), 90.0),
    ('swings', (4.6, 4.8), 35.0),
    ('carousel', (4.2, 4.2), 30.0),
    ('climber', (4.6, 4.6), 60.0),
    ('sandbox', (4.0, 4.0), 25.0),
    ('nest', (4.4, 4.6), 70.0),
    ('seesaw', (4.2, 1.8), 18.0),
    ('house', (2.8, 2.6), 15.0),
    ('spring', (1.6, 1.3), 6.0),
    ('spring', (1.6, 1.3), 6.0),
    ('spring', (1.6, 1.3), 25.0),
    ('seesaw', (4.2, 1.8), 120.0),
]


def playground(mb, poly, z, rnd, people, fence=True):
    """Play equipment in a play area (rubber surface of the genplan's №3): as many pieces as fit, the
    big ones first, each with its safety zone clear of the others and of the edge, turned to the
    area's main direction; a low picket fence round it in the playground colours with gaps to walk
    in; benches on its edge. Returns the pieces' centres."""
    r = poly.minimum_rotated_rectangle
    cs = list(r.exterior.coords)
    e1 = (cs[1][0] - cs[0][0], cs[1][1] - cs[0][1])
    e2 = (cs[2][0] - cs[1][0], cs[2][1] - cs[1][1])
    main = math.atan2(*(e1 if math.hypot(*e1) >= math.hypot(*e2) else e2)[::-1])
    placed, zones = [], []
    area = poly.area
    for name, (su, sv), amin in ITEMS:
        if area < amin:
            continue
        for tries in range(160):
            ang = main + (math.pi / 2 if rnd.random() < 0.3 else 0.0) + rnd.uniform(-0.08, 0.08)
            x0, y0, x1, y1 = poly.bounds
            p = (rnd.uniform(x0, x1), rnd.uniform(y0, y1))
            F = Frame(p[0], p[1], ang)
            zone = F.rect(-su / 2, -sv / 2, su / 2, sv / 2)
            if not poly.buffer(-0.3).contains(zone) or any(zone.intersects(q) for q in zones):
                continue
            zones.append(zone)
            WALK['solids'].append(zone.buffer(-0.45 if min(su, sv) > 2.5 else -0.15, join_style='mitre'))
            placed.append(p)
            Fz = Frame(p[0], p[1], ang)
            col = [PLAY[(len(placed) + k) % len(PLAY)] for k in range(5)]
            mbz = _Lift(mb, z)
            if name == 'tower':
                play_tower(mbz, Fz, rnd, col)
            elif name == 'swings':
                swings(mbz, Fz, col[0])
            elif name == 'nest':
                swings(mbz, Fz, col[1], nest=True)
            elif name == 'carousel':
                carousel(mbz, Fz, col[0])
            elif name == 'seesaw':
                seesaw(mbz, Fz, col[0])
            elif name == 'spring':
                spring(mbz, Fz, col[0], rnd)
            elif name == 'sandbox':
                sandbox(mbz, Fz, rnd)
            elif name == 'house':
                playhouse(mbz, Fz, col)
            elif name == 'climber':
                climber(mbz, Fz, col[0])
            for k in range(rnd.randint(0, 2)):
                people.append([round(p[0] + rnd.uniform(-1.5, 1.5), 2), round(p[1] + rnd.uniform(-1.5, 1.5), 2), z, rnd.randrange(6)])
            break
    # a low fence round the area in coloured pickets, a 1.6 m gap every 14 m
    if fence and area > 60:
        ring = poly.buffer(0.25, join_style='mitre').exterior
        L = ring.length
        t = 0.0
        k = 0
        while t < L:
            seg_end = min(L, t + 12.4)
            pts = [ring.interpolate(s) for s in np.arange(t, seg_end, 0.25)]
            for q in pts:
                mb.box(q.x, q.y, z, 0.07, 0.07, 0.75, PLAY[k % len(PLAY)])
                k += 1
            line = [ring.interpolate(s) for s in np.arange(t, seg_end + 0.01, 0.5)]
            if len(line) >= 2:
                c2 = [(q.x, q.y) for q in line]
                WALK['lines'].append([0.1, c2])
                mb.tube(c2, [z + 0.55] * len(c2), [z + 0.6] * len(c2), 0.04, 'Metal')
            t = seg_end + 1.6
    return placed


class _Lift:
    """a MeshBuilder that puts everything z higher (play pieces on the rubber surface)"""

    def __init__(self, mb, dz):
        self.mb, self.dz = mb, dz

    def face(self, pts, mat, uv=None):
        self.mb.face([(p[0], p[1], p[2] + self.dz) for p in pts], mat, uv)

    def __getattr__(self, name):
        fn = getattr(type(self.mb), name)
        return lambda *a, **k: fn(self, *a, **k)


# ----------------------------------------------------------------------------
# the kindergarten
# ----------------------------------------------------------------------------

def kindergarten(mb, wings, labels, rnd):
    """Kindergarten for 300 (№7): the genplan's three wings as drawn, three storeys of white render
    with large windows framed in the playground colours and a colour band under the roof, round the
    stepped entrance court the genplan draws between them, glass links where the wings meet."""
    floors, fh = 3, 3.5
    H = floors * fh
    shapes = [w.simplify(0.25) for w in wings if w.area > 100]
    if not shapes:
        return None
    u = unary_union([s.buffer(0.01) for s in shapes])
    cols = ['Kinder red', 'Kinder yellow', 'Kinder blue', 'Kinder green']
    for wi, w in enumerate(shapes):
        mb.prism(w.buffer(0.03, join_style='mitre'), 0.0, 0.6, 'School plinth')
        block(mb, w, 0.0, H, 'Kinder render', 'Kinder render')
        WALK['solids'].append(w.buffer(0.25, join_style='mitre'))
        band = w.buffer(0.06, join_style='mitre').difference(w.buffer(-0.2, join_style='mitre'))
        mb.prism(band, H - 0.9, H - 0.25, cols[wi % 4], cols[wi % 4])
        for k, (a, b) in enumerate(ring_edges(w)):
            if math.dist(a, b) < 5:
                continue
            window_row(mb, a, b, 0.0, floors, fh, 3.1, 2.1, 1.8, 0.75, 'Window glass', cols[(wi + k) % 4])
    # the entrance court: the steps the genplan draws in the middle, a glass hall behind them
    c = u.centroid
    hexa = Polygon([(c.x + 7.0 * math.cos(t), c.y + 7.0 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 7)[:-1] + 0.3])
    hall = hexa.difference(u.buffer(0.2))
    for q in parts(hall):
        if q.area > 6:
            WALK['solids'].append(q)
            mb.prism(q, 0.0, 4.4, 'Shop glass', 'Stone white')
            mb.prism(q.buffer(0.15, join_style='mitre').difference(q), 4.4, 4.8, 'Stone white', 'Stone white')
    labels.append(dict(x=round(c.x, 2), y=round(c.y, 2), z=H + 3, ru='Детский сад на 300 мест', tj='Боғчаи кӯдакона барои 300 ҷой', kind='kindergarten'))
    return u


def veranda(mb, poly, rnd):
    """a group's shade veranda (the genplan's small dark red rectangles by the kindergarten): a
    timber deck, posts and a pitched roof in a playground colour, benches along the back"""
    r = poly.minimum_rotated_rectangle
    cs = list(r.exterior.coords)
    e1 = (cs[1][0] - cs[0][0], cs[1][1] - cs[0][1])
    e2 = (cs[2][0] - cs[1][0], cs[2][1] - cs[1][1])
    if math.hypot(*e1) < math.hypot(*e2):
        e1, e2 = e2, e1
    L, W = math.hypot(*e1), math.hypot(*e2)
    F = Frame(r.centroid.x, r.centroid.y, math.atan2(e1[1], e1[0]))
    WALK['solids'].append(F.rect(-L / 2 - 0.05, -W / 2 - 0.05, L / 2 + 0.05, W / 2 + 0.05))
    F.box(mb, 0.0, 0.0, 0.12, L, W, 0.12, 'Wood')
    for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x, y = F(su * (L / 2 - 0.2), sv * (W / 2 - 0.2))
        cyl(mb, x, y, 0.24, 2.6, 0.08, 'Frame light', n=8)
    x, y = F(0.0, 0.0)
    gable(mb, x, y, 2.6, L + 0.6, W + 0.6, 0.9, rnd.choice(['Kinder red', 'Kinder blue', 'Kinder green']), rot=F.ang)
    F.box(mb, 0.0, W / 2 - 0.4, 0.24, L - 0.6, 0.4, 0.42, 'Wood')
    F.box(mb, 0.0, W / 2 - 0.12, 0.24, L - 0.6, 0.06, 1.0, 'Wood')


# ----------------------------------------------------------------------------
# shrubs and flower beds
# ----------------------------------------------------------------------------

def plantings(mb, lawn, avoid, rnd, z):
    """On the lawns inside the plot: groups of garden shrubs along the edges of the paths (returned
    as plants for the viewer: [x, y, z, height, radius, 'shrub']), and flower beds at the corners of
    the larger lawns (low colourful mounds edged in stone). Not where people walk, trees stand or
    the playgrounds are."""
    out, shrubs = [], []
    for q in parts(lawn):
        if q.area < 30:
            continue
        inner = q.buffer(-0.9)
        if inner.is_empty:
            continue
        ring = q.exterior
        step = 7.5 if q.area > 200 else 10.0
        for t in np.arange(rnd.uniform(0, step), ring.length, step):
            p = ring.interpolate(t)
            # half a metre into the lawn
            c = q.representative_point()
            k = 1.1 / max(1.0, p.distance(c))
            x, y = p.x + (c.x - p.x) * k, p.y + (c.y - p.y) * k
            pt = Point(x, y)
            if not inner.contains(pt) or avoid.contains(pt) or any(pt.distance(o) < 2.2 for o in out):
                continue
            out.append(pt)
            n = rnd.randint(2, 4)
            for j in range(n):
                dx, dy = rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8)
                h = rnd.uniform(0.9, 1.6)
                shrubs.append([round(x + dx, 2), round(y + dy, 2), z, round(h, 2), round(h * rnd.uniform(0.55, 0.75), 2), 'shrub'])
        if q.area > 120:
            # a flower bed: a round bed edged with stone, low flowers in two colours
            for tries in range(20):
                x0, y0, x1, y1 = inner.bounds
                p = Point(rnd.uniform(x0, x1), rnd.uniform(y0, y1))
                if not q.buffer(-2.2).contains(p) or avoid.buffer(1.0).contains(p) or any(p.distance(o) < 4 for o in out):
                    continue
                out.append(p)
                r = rnd.uniform(1.1, 1.7)
                pts = [(p.x + r * math.cos(a), p.y + r * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 20, endpoint=False)]
                mb.polygon_face(Polygon(pts), z + 0.03, 'Mulch')
                WALK['posts'].append([p.x, p.y, r + 0.1])
                mb.tube(pts, [z] * 20, [z + 0.12] * 20, 0.1, 'Kerb', closed=True)
                cA, cB = rnd.sample(['Flowers red', 'Flowers yellow', 'Flowers violet', 'Flowers white'], 2)
                for j in range(int(r * 9)):
                    a2, rr = rnd.uniform(0, 2 * math.pi), r * math.sqrt(rnd.random()) * 0.85
                    mb.blob(p.x + rr * math.cos(a2), p.y + rr * math.sin(a2), z + 0.12, 0.2, 0.2, 0.14, cA if rr < r * 0.5 else cB, subdiv=1, jitter=0.15, rnd=rnd)
                break
    return shrubs
