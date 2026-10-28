"""Block A, the glass tower, as the client renders show it.

Everything here was measured on the renders unwrapped onto the model's faces (the renders' cameras
fitted to the band rows to a pixel, tools/ab/calib.py; the pictures put onto the faces with
tools/ab/posmap.mjs + tools/ab/unwrap.py): render 1 (from the south: the -x and -y faces),
render 2 (from the north-west: +y and -x), render 4 (the close-up: -x and -y). Renders 1 and 2
give the same numbers for the two faces they share in mirror image (to 0.3-0.9 m).

The faces, by plan side (the plan's x axis points east-north-east):
  -y  (to the south-south-east)  S corner (-x) ... E corner (+x)      renders 1, 4
  +y  (to the north-north-west)  N corner (+x) ... W corner (-x)      render 2
  -x  (to the west-south-west)   W corner (+y) ... S corner (-y)      renders 1, 2, 4
  +x  (to the east-north-east)   E corner (-y) ... N corner (+y)      not on any render
Curtain wall of dark blue-green glass, mullions every 1.9 m, a thin white transom 1.1 m under each
slab and a dark one 1.9 m under it; a white band 0.76 m tall standing 0.45 m out at every slab.
On the ±y faces the bands stop 9 m short of the +x corners: the corner flats' facades are glass
all the way up, with only a dark line at each slab. On floors 4-11 that band-less zone slants
down towards the middle of the face (the bands end earlier floor by floor) and below it the
bands come back from the corner. Two-storey corner loggias, 1.8 m deep: at the W corner on floors
9-10 and 20-21 (the plan's corner terraces), at the S corner on 6-7 and 17-18. On the roof a
perforated metal screen on a dark steel frame, 10.6 m tall over the S corner, 10.2 m over the W
corner, sloping down to 2.4 m over the N corner and nothing over the E corner.
The +x face is on no render: it is made to go on from its two corners (glass above floor 9,
the lower floors' bands carried round the corners).
"""
import math

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from .config import SLAB, height, level

BAND_H = 0.76         # white slab band, centred on the floor level
BAND_OUT = 0.45       # how far it stands out of the glass
BAND_IN = 0.06        # and how far it reaches back behind the glass line
GLASS_IN = 0.05       # the glass line, behind the curtain wall box
MULLION = 1.9         # mullion pitch
TRANSOM_W = 1.1       # thin white transom: under the next slab's band centre
TRANSOM_D = 1.9       # dark transom
ROOF_BAND = (0.38, 0.9)   # the roof band: from 0.38 m under the roof level to 0.9 m over it

# where the bands of the ±y faces end, plan x (the band runs from the -x corner to there), and
# where they start again below the slanting glass zone (to the +x corner)
GLASS_FROM = 13.85
END = {4: -5.9, 5: -2.55, 6: 0.15, 7: 2.85, 8: 6.1, 9: 8.2, 10: 10.6, 11: 12.25}
START = {4: 7.75, 5: 9.85, 6: 12.25, 7: 15.05, 8: 18.15, 9: 20.65}
# dark strips running up the glass (where flats meet the facade): centre, width, by face
STRIPS = {'-y': [(-13.45, 0.5), (13.35, 0.5)], '+y': [(-13.45, 0.5), (13.35, 0.5)],
          '-x': [(9.1, 0.5), (-5.6, 0.5)], '+x': []}
# corner loggias: corner, floors (the lower of each pair first), extents along the two faces
# (plan x to, plan y from/to), depth to the back walls (the plan's terraces: 1.8 m)
LOGGIAS = [
    dict(corner='W', floors=((9, 10), (20, 21)), x_to=-13.7, y_from=14.6),
    dict(corner='S', floors=((6, 7), (17, 18)), x_to=-13.8, y_to=-12.65),
]
LOGGIA_BACK = 20.2    # the back walls: |x| = 20.2 and |y| = 20.2 (the plan's terraces, 1.8 m deep)
# crown height (top of the screen) over each corner, metres above the roof level
CROWN = {'S': 11.25, 'W': 10.2, 'N': 2.95, 'E': 0.7}
CROWN_POST = 3.4      # post pitch
CROWN_RAILS = (2.9, 6.7)  # horizontal rails, above the roof level


def outline(plan):
    """The curtain wall: a plain box round the plan (its facade line has small jogs the glass
    runs straight past)."""
    x0, y0, x1, y1 = Polygon(plan['enclosure']).buffer(0).buffer(-0.8, join_style='mitre').buffer(0.8, join_style='mitre').bounds
    return x0 - 0.12, y0 - 0.12, x1 + 0.12, y1 + 0.12


def faces(B):
    """(name, start point, end point, outward normal, plan axis of t) of the four faces, each
    running left to right seen from outside"""
    x0, y0, x1, y1 = B
    return [('-y', (x0, y0), (x1, y0), (0, -1), 0), ('+x', (x1, y0), (x1, y1), (1, 0), 1),
            ('+y', (x1, y1), (x0, y1), (0, 1), 0), ('-x', (x0, y1), (x0, y0), (-1, 0), 1)]


def loggia_floors():
    out = {}
    for lg in LOGGIAS:
        for pair in lg['floors']:
            for f in pair:
                out.setdefault(f, []).append((lg, pair))
    return out


LOGGIA_AT = loggia_floors()


def loggia_spans(B, f):
    """the openings of the corner loggias on floor f: {face: [(t0, t1)]} and their L polygons"""
    x0, y0, x1, y1 = B
    spans, polys = {}, []
    for lg, pair in LOGGIA_AT.get(f, []):
        if lg['corner'] == 'W':
            spans.setdefault('+y', []).append((x0, lg['x_to']))
            spans.setdefault('-x', []).append((lg['y_from'], y1))
            polys.append(unary_union([box(x0, LOGGIA_BACK, lg['x_to'], y1), box(x0, lg['y_from'], -LOGGIA_BACK, y1)]))
        else:
            spans.setdefault('-y', []).append((x0, lg['x_to']))
            spans.setdefault('-x', []).append((y0, lg['y_to']))
            polys.append(unary_union([box(x0, y0, lg['x_to'], -LOGGIA_BACK), box(x0, y0, -LOGGIA_BACK, lg['y_to'])]))
    return spans, polys


def band_runs(B, face, f, roof=False):
    """intervals of the plan coordinate along `face` where floor f's white band runs"""
    x0, y0, x1, y1 = B
    if face in ('-y', '+y'):
        if roof:
            return [(x0, GLASS_FROM)]
        if f == 3:
            return [(x0, x1)]
        if f in END:
            return [(x0, END[f])] + ([(START[f], x1)] if f in START else [])
        return [(x0, GLASS_FROM)]
    if face == '-x':
        return [(y0, y1)]
    # +x: not on the renders; carried on from the corners (bands up to floor 9, glass above)
    return [] if roof or f > 9 else [(y0, y1)]


def _cut(runs, holes):
    """runs less the holes (all intervals as (a, b), a < b)"""
    out = []
    for a, b in runs:
        segs = [(min(a, b), max(a, b))]
        for h0, h1 in holes:
            h0, h1 = min(h0, h1), max(h0, h1)
            nxt = []
            for s0, s1 in segs:
                if h1 <= s0 or h0 >= s1:
                    nxt.append((s0, s1))
                    continue
                if h0 > s0:
                    nxt.append((s0, h0))
                if h1 < s1:
                    nxt.append((h1, s1))
            segs = nxt
        out += [s for s in segs if s[1] - s[0] > 0.05]
    return out


def band_polygons(B, f, roof=False, skip=None):
    """the white band of floor f as plan polygons: one strip per run, joined round the corners
    where both faces' bands reach them"""
    x0, y0, x1, y1 = B
    o, i = BAND_OUT, BAND_IN
    polys = []
    reach = {}   # corner -> faces whose band reaches it
    for name, a, b, n, ax in faces(B):
        runs = band_runs(B, name, f, roof)
        if skip and name in skip:
            runs = _cut(runs, skip[name])
        for r0, r1 in runs:
            if name in ('-y', '+y'):
                yy = y0 if name == '-y' else y1
                y_out = yy - o if name == '-y' else yy + o
                y_in = yy + i if name == '-y' else yy - i
                polys.append(box(r0, min(y_out, y_in), r1, max(y_out, y_in)))
                for xc, c in ((x0, 'S' if name == '-y' else 'W'), (x1, 'E' if name == '-y' else 'N')):
                    if abs(min(r0, r1) - xc) < 0.01 or abs(max(r0, r1) - xc) < 0.01:
                        reach.setdefault(c, set()).add(name)
            else:
                xx = x0 if name == '-x' else x1
                x_out = xx - o if name == '-x' else xx + o
                x_in = xx + i if name == '-x' else xx - i
                polys.append(box(min(x_out, x_in), r0, max(x_out, x_in), r1))
                for yc, c in ((y0, 'S' if name == '-x' else 'E'), (y1, 'W' if name == '-x' else 'N')):
                    if abs(min(r0, r1) - yc) < 0.01 or abs(max(r0, r1) - yc) < 0.01:
                        reach.setdefault(c, set()).add(name)
    corners = {'S': (x0, y0, -1, -1), 'E': (x1, y0, 1, -1), 'N': (x1, y1, 1, 1), 'W': (x0, y1, -1, 1)}
    for c, fs in reach.items():
        if len(fs) == 2:
            cx, cy, sx, sy = corners[c]
            polys.append(box(min(cx, cx + sx * o), min(cy, cy + sy * o), max(cx, cx + sx * o), max(cy, cy + sy * o)))
    return unary_union(polys) if polys else Polygon()


def glass_runs(B, name, f):
    """the face's glass (curtain wall) intervals on floor f: the whole face less the loggias"""
    x0, y0, x1, y1 = B
    t0, t1 = (x0, x1) if name in ('-y', '+y') else (y0, y1)
    spans, _ = loggia_spans(B, f)
    return _cut([(t0, t1)], spans.get(name, []))


def banded(B, name, f, t):
    """is the glass at t on this face under a white band (for the thin white transoms)?"""
    for r0, r1 in band_runs(B, name, f + 1):
        if min(r0, r1) - 0.01 <= t <= max(r0, r1) + 0.01:
            return True
    return False


def _pt(name, B, t, off):
    """plan point on face `name` at coordinate t, `off` out of the curtain wall line"""
    x0, y0, x1, y1 = B
    if name == '-y':
        return (t, y0 - off)
    if name == '+y':
        return (t, y1 + off)
    if name == '-x':
        return (x0 - off, t)
    return (x1 + off, t)


def curtain(mb, B, f, h):
    """glass, mullions, transoms and dark strips of floor f (z = 0 at the floor level)"""
    for name, a, b, n, ax in faces(B):
        sgn = 1 if name in ('-y', '+x') else -1      # t grows left to right seen from outside
        rot = math.atan2(b[1] - a[1], b[0] - a[0])
        for g0, g1 in glass_runs(B, name, f):
            # glass in the face plane (one quad per run, left to right seen from outside)
            ta, tb = (g0, g1) if sgn > 0 else (g1, g0)
            pa, pb = _pt(name, B, ta, -GLASS_IN), _pt(name, B, tb, -GLASS_IN)
            mb.quad_wall(pa, pb, 0.0, h, 'Tower glass', u0=0.0)
            # mullions on a pitch from the face's start corner, at the run's ends too
            t_start = a[ax]
            ts = {round(g0, 3), round(g1, 3)}
            k = 0
            while True:
                t = t_start + sgn * MULLION * k
                if (sgn > 0 and t > max(g0, g1)) or (sgn < 0 and t < min(g0, g1)):
                    break
                if min(g0, g1) < t < max(g0, g1):
                    ts.add(round(t, 3))
                k += 1
            for t in ts:
                p = _pt(name, B, t, -GLASS_IN + 0.04)
                mb.box(p[0], p[1], 0.0, 0.06 if ax == 0 else 0.1, 0.1 if ax == 0 else 0.06, h, 'Frame dark')
            # transoms: thin white 1.1 m under the next band where bands run, a dark one under it
            lo, hi = min(g0, g1), max(g0, g1)
            cuts = sorted({lo, hi} | {t for t in ts if lo < t < hi})
            for s0, s1 in zip(cuts, cuts[1:]):
                m = (s0 + s1) / 2
                L = s1 - s0
                pm = _pt(name, B, m, -GLASS_IN + 0.05)
                sx, sy = (L, 0.1) if ax == 0 else (0.1, L)
                if banded(B, name, f, m):
                    mb.box(pm[0], pm[1], h - TRANSOM_W - 0.07, sx, sy, 0.14, 'White band')
                mb.box(pm[0], pm[1], h - TRANSOM_D - 0.03, sx, sy, 0.06, 'Frame dark')
        # dark strips up the glass (in front of it, behind the bands)
        for c, w in STRIPS[name]:
            if any(min(g0, g1) <= c <= max(g0, g1) for g0, g1 in glass_runs(B, name, f)):
                p = _pt(name, B, c, -GLASS_IN + 0.07)
                mb.box(p[0], p[1], 0.0, w if ax == 0 else 0.08, 0.08 if ax == 0 else w, h, 'Strip dark')


def slab_lines(mb, B, f, roof=False):
    """a dark line at the slab where no white band runs (the glass zones)"""
    x0, y0, x1, y1 = B
    spans, _ = loggia_spans(B, f)
    spans_below, _ = loggia_spans(B, f - 1)
    for name, a, b, n, ax in faces(B):
        t0, t1 = (x0, x1) if ax == 0 else (y0, y1)
        free = _cut([(t0, t1)], band_runs(B, name, f, roof) + spans.get(name, []) + spans_below.get(name, []))
        for r0, r1 in free:
            m, L = (r0 + r1) / 2, r1 - r0
            p = _pt(name, B, m, 0.02)
            sx, sy = (L, 0.16) if ax == 0 else (0.16, L)
            mb.box(p[0], p[1], -0.18, sx, sy, 0.36, 'Frame dark')


def loggias(mb, B, f, h):
    """the corner loggias of floor f: back walls with doors, white returns, soffit, railing"""
    spans, polys = loggia_spans(B, f)
    x0, y0, x1, y1 = B
    for lg, pair in LOGGIA_AT.get(f, []):
        lower = f == pair[0]
        if lg['corner'] == 'W':
            xa, ya = lg['x_to'], lg['y_from']
            # back wall facing +y (behind the +y face opening): y = LOGGIA_BACK, x from x0+... to xa
            backs = [((xa, LOGGIA_BACK), (-LOGGIA_BACK, LOGGIA_BACK)), ((-LOGGIA_BACK, LOGGIA_BACK), (-LOGGIA_BACK, ya))]
            returns = [((xa, y1), (xa, LOGGIA_BACK)), ((x0, ya), (-LOGGIA_BACK, ya))]
            rail = [(xa, y1 - 0.08), (x0 + 0.08, y1 - 0.08), (x0 + 0.08, ya)]
        else:
            xa, ya = lg['x_to'], lg['y_to']
            backs = [((-LOGGIA_BACK, -LOGGIA_BACK), (xa, -LOGGIA_BACK)), ((-LOGGIA_BACK, ya), (-LOGGIA_BACK, -LOGGIA_BACK))]
            returns = [((xa, -LOGGIA_BACK), (xa, y0)), ((-LOGGIA_BACK, ya), (x0, ya))]
            rail = [(x0 + 0.08, ya), (x0 + 0.08, y0 + 0.08), (xa, y0 + 0.08)]
        # back walls: dark grey render, glazed doors in white frames (two or three per wall)
        for p, q in backs:
            L = math.dist(p, q)
            ux, uy = (q[0] - p[0]) / L, (q[1] - p[1]) / L
            nx, ny = uy, -ux
            mb.quad_wall(p, q, 0.0, h, 'Loggia wall')
            n_doors = 2 if L > 6 else 1
            for k in range(n_doors):
                s = L * (k + 1) / (n_doors + 1)
                c = (p[0] + ux * s + nx * 0.02, p[1] + uy * s + ny * 0.02)
                rot = math.atan2(uy, ux)
                mb.box(c[0], c[1], 0.0, 1.5, 0.06, 2.45, 'Frame light', rot=rot)
                g = (c[0] + nx * 0.035, c[1] + ny * 0.035)
                mb.box(g[0], g[1], 0.06, 1.38, 0.02, 2.33, 'Window glass', rot=rot)
                mb.box(g[0] + nx * 0.02, g[1] + ny * 0.02, 0.06, 0.06, 0.02, 2.33, 'Frame light', rot=rot)
        # white returns at the inner ends, from the glass line to the back wall
        for p, q in returns:
            L = math.dist(p, q)
            mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            rot = math.atan2(q[1] - p[1], q[0] - p[0])
            mb.box(mid[0], mid[1], 0.0, L, 0.3, h, 'White band', rot=rot)
        # the loggia floor; the soffit of the slab above (dark grey render)
        mine = [g for g, (l2, _) in zip(polys, LOGGIA_AT.get(f, [])) if l2 is lg]
        for g in mine:
            mb.polygon_face(g, SLAB + 0.01, 'Deck paving')
            if not lower:
                mb.polygon_face(g, h - 0.26, 'Loggia soffit', up=False)
        # glass railing on a dark base, a dark top rail
        zb = SLAB
        mb.tube(rail, [zb] * len(rail), [zb + 0.12] * len(rail), 0.12, 'Frame dark')
        mb.ribbon(rail, zb + 0.12, zb + 1.08, 'Railing glass', double=True)
        mb.tube(rail, [zb + 1.06] * len(rail), [zb + 1.12] * len(rail), 0.07, 'Frame dark')
        for p in rail:
            mb.box(p[0], p[1], zb, 0.06, 0.06, 1.1, 'Frame dark')
        if not lower:
            continue
        # the slab between the two loggia levels: its edge light grey, set back from the band line
        # (renders 1 and 2: no white band there; render 4: a lighter edge in the sun)
        for g in mine:
            mb.prism(g.buffer(-0.12, join_style='mitre'), h - 0.39, h + SLAB, 'Loggia slab', None, 'Loggia soffit')


def floor_meshes(b, plan, f, mats, name, MeshBuilder):
    """(slab mesh, walls mesh) of tower floor f, z = 0 at its floor level"""
    h = height(f, b)
    B = outline(plan)
    x0, y0, x1, y1 = B
    mb = MeshBuilder()
    floor = box(x0 + 0.06, y0 + 0.06, x1 - 0.06, y1 - 0.06)
    _, lps = loggia_spans(B, f)
    mb.prism(floor, -0.25, SLAB, 'Frame dark', 'Shop floor', 'Frame dark')
    # the band at this slab (the middle slab of a loggia keeps no white band there)
    skip = {}
    for lg, pair in LOGGIA_AT.get(f, []):
        if f == pair[1]:
            sp, _ = loggia_spans(B, f)
            for k, v in sp.items():
                skip.setdefault(k, []).extend(v)
    bands = band_polygons(B, f, skip=skip)
    mb.prism_chamfer(bands, -BAND_H / 2, BAND_H / 2, 'White band', 'White band', 'White band', c=0.03)
    slab_lines(mb, B, f)
    slab_mesh = mb.to_mesh(f'{name} slab', mats)
    mb = MeshBuilder()
    curtain(mb, B, f, h)
    loggias(mb, B, f, h)
    return slab_mesh, mb.to_mesh(f'{name} walls', mats)


def look_of(f):
    """everything about floor f that changes its facade (floors alike share their meshes)"""
    return ('glassA', f in END, f in START, f, ) if (f in END or f in LOGGIA_AT or f == 3) else ('glassA', 'typical')


# ----------------------------------------------------------------------------
# roof: the roof band, the dark parapet of the glass zones, the crown screen
# ----------------------------------------------------------------------------

def crown_top(B, p):
    """height of the crown's top over plan point p on the box, above the roof level"""
    x0, y0, x1, y1 = B
    u = (p[0] - x0) / (x1 - x0)
    v = (p[1] - y0) / (y1 - y0)
    S, E, N, W = CROWN['S'], CROWN['E'], CROWN['N'], CROWN['W']
    return (1 - u) * (1 - v) * S + u * (1 - v) * E + u * v * N + (1 - u) * v * W


def build_roof(mb, b, plan, zr):
    B = outline(plan)
    x0, y0, x1, y1 = B
    # roof slab, the roof band (white where the faces have bands, dark over the glass zones)
    mb.prism(box(x0 + 0.06, y0 + 0.06, x1 - 0.06, y1 - 0.06), zr - 0.25, zr + 0.3, 'White band', 'Roof', None)
    bands = band_polygons(B, 25, roof=True)
    mb.prism_chamfer(bands, zr - ROOF_BAND[0], zr + ROOF_BAND[1], 'White band', 'White band', 'White band', c=0.03)
    ring = box(x0, y0, x1, y1).difference(box(x0 + 0.35, y0 + 0.35, x1 - 0.35, y1 - 0.35))
    dark = ring.difference(bands.buffer(0.02))
    mb.prism(dark, zr - 0.2, zr + 1.6, 'Frame crown', 'Frame crown')
    # plant room in the middle
    c = ((x0 + x1) / 2, (y0 + y1) / 2)
    mb.box(c[0], c[1], zr + 0.3, 16.0, 12.0, 4.0, 'Plant room')
    # the crown: posts on a 3.4 m pitch round the box, perforated panels between them, two level
    # rails, a top rail following the slope, a small curved bracket at the foot of each post
    zb = zr + ROOF_BAND[1]
    pts = []
    for name, a, bb, n, ax in faces(B):
        L = math.dist(a, bb)
        k = max(1, round(L / CROWN_POST))
        for i in range(k):
            t = i / k
            pts.append((a[0] + (bb[0] - a[0]) * t + n[0] * 0.15, a[1] + (bb[1] - a[1]) * t + n[1] * 0.15))
    tops = [zr + max(crown_top(B, p), ROOF_BAND[1] + 0.25) for p in pts]
    closed = pts + pts[:1]
    tz = tops + tops[:1]
    # the perforated panels, both sides, with UVs in metres (the viewer's perforation pattern)
    u = 0.0
    for i in range(len(closed) - 1):
        a, c = closed[i], closed[i + 1]
        L = math.dist(a, c)
        q = [(a[0], a[1], zb), (c[0], c[1], zb), (c[0], c[1], tz[i + 1] - 0.05), (a[0], a[1], tz[i] - 0.05)]
        uv = [(u, zb), (u + L, zb), (u + L, tz[i + 1] - 0.05), (u, tz[i] - 0.05)]
        mb.face(q, 'Mesh screen', uv)
        mb.face(q[::-1], 'Mesh screen', uv[::-1])
        u += L
    for p, t in zip(pts, tops):
        if t - zb > 0.4:
            mb.box(p[0], p[1], zb, 0.22, 0.22, t - zb, 'Frame crown')
    mb.tube(closed, [t - 0.16 for t in tz], tz, 0.16, 'Frame crown')
    mb.tube(closed, [zb] * len(closed), [zb + 0.14] * len(closed), 0.16, 'Frame crown')
    for zrail in CROWN_RAILS:
        z = zr + zrail
        seg = []
        for p, t in zip(closed, tz):
            if t > z + 0.15:
                seg.append(p)
            elif len(seg) > 1:
                mb.tube(seg, [z - 0.07] * len(seg), [z + 0.07] * len(seg), 0.14, 'Frame crown')
                seg = []
            else:
                seg = []
        if len(seg) > 1:
            mb.tube(seg, [z - 0.07] * len(seg), [z + 0.07] * len(seg), 0.14, 'Frame crown')
    # curved brackets at the foot of the posts (render 4)
    n = len(pts)
    for i, p in enumerate(pts):
        if tops[i] - zb < 2.0:
            continue
        for j in (i - 1, (i + 1) % n):
            q = pts[j]
            d = math.dist(p, q)
            if d < 1:
                continue
            ux, uy = (q[0] - p[0]) / d, (q[1] - p[1]) / d
            r, w = 1.1, 0.07
            P3 = lambda al, z: (p[0] + ux * al, p[1] + uy * al, z)
            for k in range(8):
                a0, a1 = math.radians(90 * k / 8), math.radians(90 * (k + 1) / 8)
                quad = []
                for a, rr in ((a0, r), (a1, r), (a1, r + w), (a0, r + w)):
                    quad.append(P3(r - rr * math.cos(a), zb + r - rr * math.sin(a)))
                mb.face(quad, 'Frame crown')
                mb.face(quad[::-1], 'Frame crown')
