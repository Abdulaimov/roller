"""Furniture, sanitary ware and lifts as the architect drew them on the plan sheets.

Every symbol on the sheets is an AutoCAD block drawn as a run of consecutive drawing commands
(tools/ab/blocks.py finds the runs). A run is split into the pieces it holds (by line style and by
what touches what), each piece is told apart by its make-up and size and becomes an item for the
viewer, in plan metres. Angles are plan angles (radians); `f` is where the front of a piece faces;
"frame x" is the viewer's x for a piece (src/interior/kit.js): plan direction (-sin f, cos f).

  bed       c, w (width), l (length), f (head to foot), stands [[x, y, w, d], ...] (nightstands)
  tv        TV unit against a wall: c, w (along the wall), d, f (into the room)
  kitchen   the run along a wall: c, w, d, f, sink / hob (frame x of their middles), bowls
  dining    table c, w, d, a (angle of its long side); chairs [[x, y, facing], ...]
  rug       c, w, d, a
  sofa      corner sofa as boxes [[cx, cy, w, d, z0, z1, a, part], ...] (part: seat, back, arm)
  armchair  c, w, d, f
  ctable    coffee table c, w, d, a, h
  toilet    c, w, d, f (from the cistern to the bowl)
  basin     c, w, d, f
  bath      c, w (its length, along the wall), d, f (out into the room), tap (+1 / -1 frame x)
  ac        air-conditioner unit on a loggia: c, w, d, f

Lifts (plan['lifts']): c, w (along the door wall), d, f (out of the doors), q (kg). The doors are
across the car from its counterweight (the small box drawn at the back of the car).

    tools/ab/py tools/ab/furniture.py KEY OUT.png    # the items drawn over the sheet, to check them
"""
import math
import os
import sys

import numpy as np
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.ops import nearest_points, polygonize, unary_union

sys.path.insert(0, os.path.dirname(__file__))
import blocks as B  # noqa: E402

import extract_plan as E  # noqa: E402  (not B.E: run as a script, blocks is not loaded yet)
LIFT_RED = (0.66, 0.06, 0.01)
# lift capacities by the length of the car's door wall (as labelled on the sheets)
LIFT_Q = {'BG': [(2.2, 1000), (1.9, 800), (1.7, 630)], 'A': [(2.5, 1500), (1.7, 800)]}

# the living-room set (rug, corner sofa, two armchairs, two nesting tables) is one block, drawn
# turned and mirrored: its pieces in the frame of the block's bounding box, read off the canonical
# instance (BG #20384: box centre (-28.806, 5.234), long side along +x, 2.93 x 2.34 m)
LIVING_CANON = ('BG', 20384)
LIVING = dict(
    rug=dict(x0=-1.164, x1=1.069, y0=-1.074, y1=1.019),
    sofa=dict(x0=-0.397, x1=1.403, y0=0.533, y1=1.169),        # three seats, the back along +y
    chaise=dict(x0=0.786, x1=1.353, y0=-0.067, y1=0.533),       # the chaise at its +x end, open to -y
    chairs=[dict(c=(-1.139, 0.233), f=0.0), dict(c=(1.053, -0.767), f=135.0)],
    tables=[dict(x0=-0.297, x1=0.369, y0=-0.334, y1=0.199, h=0.42), dict(x0=-0.614, x1=-0.131, y0=-0.701, y1=-0.001, h=0.36)],
)
ARM = 0.14   # sofa arm width
BACK = 0.2   # sofa back depth


# ---------------------------------------------------------------------------- geometry

def obb(pts):
    """oriented box of points: centre c, long side L along u, short side W along v (u turned +90 deg)"""
    r = MultiPoint(pts).minimum_rotated_rectangle
    if r.geom_type != 'Polygon':
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return dict(c=((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2), L=max(max(xs) - min(xs), max(ys) - min(ys)), W=0.0,
                    u=(1.0, 0.0), v=(0.0, 1.0))
    cs = list(r.exterior.coords)[:4]
    e1, e2 = math.dist(cs[0], cs[1]), math.dist(cs[1], cs[2])
    a, b = (cs[0], cs[1]) if e1 >= e2 else (cs[1], cs[2])
    L = max(e1, e2)
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    if u[0] < -1e-6 or (abs(u[0]) <= 1e-6 and u[1] < 0):   # one sign for all: u points to +x (or +y)
        u = (-u[0], -u[1])
    c = r.centroid
    return dict(c=(c.x, c.y), L=L, W=min(e1, e2), u=u, v=(-u[1], u[0]))


def local(o, p):
    dx, dy = p[0] - o['c'][0], p[1] - o['c'][1]
    return (dx * o['u'][0] + dy * o['u'][1], dx * o['v'][0] + dy * o['v'][1])


def world(o, a, b):
    return (o['c'][0] + a * o['u'][0] + b * o['v'][0], o['c'][1] + a * o['u'][1] + b * o['v'][1])


def wdir(o, a, b):
    return (a * o['u'][0] + b * o['v'][0], a * o['u'][1] + b * o['v'][1])


ang = lambda d: math.atan2(d[1], d[0])
frame_x = lambda f: (-math.sin(f), math.cos(f))
R = lambda v, n=3: round(float(v), n)
RP = lambda p: [R(p[0]), R(p[1])]


def bbox_of(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def side_gap(o, solid, axis, sign):
    """how far the solid is from one side of the box (the second nearest of a few probes along that
    side: a wall along most of the side, not just at a corner)"""
    half = o['W'] / 2 if axis == 'u' else o['L'] / 2
    ds = []
    for k in range(5):
        t = (k / 4 - 0.5) * 2 * half * 0.8
        p = world(o, sign * (o['L'] / 2 + 0.01), t) if axis == 'u' else world(o, t, sign * (o['W'] / 2 + 0.01))
        ds.append(solid.distance(Point(p)))
    ds.sort()
    return ds[1]


def against_wall(o, solid, axes):
    """the side of the box nearest a wall among the sides across `axes`: (axis, sign, gap)"""
    best = None
    for axis in axes:
        for sign in (1, -1):
            g = side_gap(o, solid, axis, sign)
            if best is None or g < best[2] - 1e-9:
                best = (axis, sign, g)
    return best


def wall_item(kind, o, axis, sign, **extra):
    """an item whose back is the side of box o at sign * (half size) along axis"""
    if axis == 'v':
        w, d, f = o['L'], o['W'], wdir(o, 0, -sign)
    else:
        w, d, f = o['W'], o['L'], wdir(o, -sign, 0)
    return dict(type=kind, c=RP(o['c']), w=R(w), d=R(d), f=R(ang(f), 4), **extra)


# ---------------------------------------------------------------------------- splitting runs

def item_shape(item):
    _, k, subs, _ = item
    if k == 'fill':
        gs = [Polygon(s).buffer(0) for s in subs if len(s) >= 3]
        gs = [g for g in gs if g.area > 1e-7]
        return unary_union(gs).buffer(0.01) if gs else None
    return unary_union([LineString(s).buffer(0.015) for s in subs if len(s) >= 2])


def as_block(items, family):
    nb = B.Block(items[0][0])
    for i, k, subs, curve in items:
        nb.add(i, k, subs, curve, bbox_of([p for s in subs for p in s]))
    nb.family = family
    return nb


def split_runs(blocks):
    """one piece per block: by line style (sanitary ware, dining hairlines, the rest), the rest by
    what touches what (a TV unit drawn next to the sofa set is a piece of its own); door symbols
    (a leaf and its swing) are dropped"""
    out = []
    for b in blocks:
        fam = {}
        for it in b.items:
            f = 'tan' if it[1] == 'tan' else 'k06' if it[1] == 'k06' else 'main'
            fam.setdefault(f, []).append(it)
        for f, items in fam.items():
            if f != 'main':
                out.append(as_block(items, f))
                continue
            shapes = [item_shape(it) for it in items]
            U = unary_union([s for s in shapes if s is not None])
            comps = list(getattr(U, 'geoms', [U]))
            groups = [[] for _ in comps]
            for it, s in zip(items, shapes):
                if s is None:
                    continue
                p = s.representative_point()
                k = next((j for j, g in enumerate(comps) if g.contains(p)), None)
                if k is None:
                    k = min(range(len(comps)), key=lambda j: comps[j].distance(p))
                groups[k].append(it)
            for g in groups:
                if g:
                    out.append(as_block(sorted(g, key=lambda it: it[0]), 'main'))
    keep = []
    for b in out:
        c = b.counts
        if b.family == 'main' and set(c) == {'k72'} and c['k72'] <= 12 and any(it[3] for it in b.items):
            o = obb(b.points())
            if o and o['L'] <= 1.4:
                continue
        keep.append(b)
    return keep


# ---------------------------------------------------------------------------- sanitary ware

def marks(part, size=0.09):
    """the small details of a fitting (tap, drain, flush button): centres of the tiny closed
    sub-paths (not the short arcs an outline may be drawn in)"""
    out = []
    for _, _, subs, _ in part:
        for s in subs:
            x0, y0, x1, y1 = bbox_of(s)
            if max(x1 - x0, y1 - y0) < size and len(s) >= 5 and math.dist(s[0], s[-1]) < 0.004:
                out.append(((x0 + x1) / 2, (y0 + y1) / 2))
    return out


# typical make-up of each fitting on these sheets: strokes, length x width
SAN_TYPICAL = {'toilet': (10, 0.73, 0.36), 'basin': (22, 0.6, 0.45), 'bath': (15, 1.65, 0.63)}


def san_kind(part):
    """(kind, box, cost) of a run of strokes that is one fitting, else (None, box, 0); cost: how far
    it is from the typical make-up of its kind"""
    pts = [p for _, _, subs, _ in part for s in subs for p in s]
    if len(pts) < 3:
        return None, None, 0
    o = obb(pts)
    L, W, n = o['L'], o['W'], len(part)
    kind = None
    if L >= 1.3 and 0.5 <= W <= 0.95 and 12 <= n <= 18:
        kind = 'bath'
    elif 0.55 <= L <= 0.85 and 0.28 <= W <= 0.5 and L / max(W, 1e-6) >= 1.4 and 5 <= n <= 12:
        kind = 'toilet'
    elif 0.38 <= L <= 0.8 and 0.3 <= W <= 0.62 and 18 <= n <= 26:
        kind = 'basin'
    if not kind:
        return None, o, 0
    tn, tl, tw = SAN_TYPICAL[kind]
    cost = abs(n - tn) * 0.2 + (0 if kind == 'bath' else 10 * (abs(L - tl) + abs(W - tw)))
    return kind, o, cost


def sanitary(b, solid):
    """the fittings of a run of sanitary strokes: a run may hold a bath, a basin and a WC drawn one
    after another - the split that explains the most strokes with fittings of the right sizes"""
    seq = b.items
    n = len(seq)
    best = [(0, 0, 0, [])] * (n + 1)   # (strokes explained, -fittings, -cost, [(kind, o, part)])
    for i in range(1, n + 1):
        cand = best[i - 1]
        for j in range(max(0, i - 30), i - 3):
            k, o, cost = san_kind(seq[j:i])
            if k:
                c = (best[j][0] + i - j, best[j][1] - 1, best[j][2] - cost, best[j][3] + [(k, o, seq[j:i])])
                if c[:3] > cand[:3]:
                    cand = c
        best[i] = cand
    best = [(b0, b1, b3) for b0, b1, b2, b3 in best]
    out = []
    for k, o, part in best[n][2]:
        m = marks(part)
        far = max(m, key=lambda p: max(abs(local(o, p)[0]) / (o['L'] / 2), abs(local(o, p)[1]) / max(o['W'] / 2, 1e-6))) if m else None
        if k == 'toilet':
            # the cistern end has the flush button
            if far is not None and abs(local(o, far)[0]) > 0.1:
                it = wall_item('toilet', o, 'u', 1 if local(o, far)[0] > 0 else -1)
            else:
                it = wall_item('toilet', o, *against_wall(o, solid, ['u'])[:2])
        elif k == 'basin':
            # the tap at the back, against the wall
            if far is not None:
                la, lb = local(o, far)
                if abs(la) / (o['L'] / 2) > abs(lb) / (o['W'] / 2):
                    it = wall_item('basin', o, 'u', 1 if la > 0 else -1)
                else:
                    it = wall_item('basin', o, 'v', 1 if lb > 0 else -1)
            else:
                it = wall_item('basin', o, *against_wall(o, solid, ['v', 'u'])[:2])
        else:
            axis, sign, _ = against_wall(o, solid, ['v'])
            it = wall_item('bath', o, axis, sign)
            # the tap end: where the drain and the mixer are drawn
            fx = frame_x(it['f'])
            if far is not None:
                d = (far[0] - o['c'][0], far[1] - o['c'][1])
                it['tap'] = 1 if d[0] * fx[0] + d[1] * fx[1] > 0 else -1
            else:
                it['tap'] = 1
        out.append(it)
    return out, sum(len(p) for _, _, p in best[n][2]), n


# ---------------------------------------------------------------------------- furniture

def groups_of(polys, gap=0.02):
    U = unary_union([p.buffer(gap) for p in polys])
    return [g.buffer(-gap) for g in getattr(U, 'geoms', [U])]


def bed(b, solid):
    """the bed block: the bed between two nightstands, the outline round all three; the stands are
    found by the lamps drawn on them (small circles), the bed is what is between them"""
    o = obb(b.points())
    lamps = []
    for _, k, subs, curve in b.items:
        if k != 'k72' or not curve:
            continue
        for sb in subs:
            x0, y0, x1, y1 = bbox_of(sb)
            if len(sb) >= 15 and 0.06 < max(x1 - x0, y1 - y0) < 0.16 and math.dist(sb[0], sb[-1]) < 0.01:
                lamps.append(local(o, ((x0 + x1) / 2, (y0 + y1) / 2)))
    # the stands stand at both ends of the long side, at the head
    if len(lamps) >= 2:
        mb = sum(p[1] for p in lamps) / len(lamps)
        head = 1 if mb > 0 else -1
    else:
        _, head, _ = against_wall(o, solid, ['v'])
    f = wdir(o, 0, -head)
    l = o['W']
    st = []
    if len(lamps) >= 2:
        # each stand from the block's end to the bed, as deep as it is wide
        sw = min(0.6, max(0.35, min(o['L'] / 2 - abs(p[0]) for p in lamps) * 2))
        for la, lb in lamps:
            ca = math.copysign(o['L'] / 2 - sw / 2, la)
            cb = head * (o['W'] / 2 - sw / 2)
            c = world(o, ca, cb)
            st.append([R(c[0]), R(c[1]), R(sw), R(sw)])
        w = o['L'] - 2 * sw - 0.04
    else:
        w = min(o['L'], 1.8)
    return dict(type='bed', c=RP(o['c']), w=R(w), l=R(l), f=R(ang(f), 4), stands=st)


def kitchen(b, solid):
    o = obb(b.points(['k12', 'fill']))
    axis, sign, _ = against_wall(o, solid, ['v'])
    it = wall_item('kitchen', o, axis, sign)
    fx = frame_x(it['f'])
    X = lambda g: (g.centroid.x - o['c'][0]) * fx[0] + (g.centroid.y - o['c'][1]) * fx[1]
    faces = [g for g in polygonize(unary_union(b.lines(['k12']))) if 0.005 < g.area < 0.6]
    # the sink: the bowls, each a nest of rounded outlines (24 x 17 to 36 x 28 cm, many points)
    rings = []
    for g in faces:
        m = obb(list(g.exterior.coords))
        if len(g.exterior.coords) >= 20 and 0.2 <= m['L'] <= 0.4 and 0.14 <= m['W'] <= 0.32:
            rings.append(X(g))
    bowls = []
    for x in sorted(rings):
        if bowls and x - bowls[-1][-1] < 0.06:
            bowls[-1].append(x)
        else:
            bowls.append([x])
    bowls = [sum(b) / len(b) for b in bowls]
    if bowls:
        it['sink'] = R(sum(bowls) / len(bowls))
        it['bowls'] = 2 if bowls[-1] - bowls[0] > 0.15 else 1
    # the cooker: a nest of squares, the biggest cluster of faces away from the sink
    xs = sorted(X(g) for g in faces if 'sink' not in it or abs(X(g) - it['sink']) > 0.35)
    best = []
    for x0 in xs:
        near = [x for x in xs if abs(x - x0) < 0.06]
        if len(near) > len(best):
            best = near
    if len(best) >= 3:
        it['hob'] = R(sum(best) / len(best))
    return it


def dining(b):
    lines = b.lines(['k06'])
    # the table: the biggest outline (a rectangle); the chairs: the small open boxes round it
    boxes = [(obb(list(l.coords)), l) for l in lines]
    to, tl = max(boxes, key=lambda t: t[0]['L'] * t[0]['W'])
    if to['L'] * to['W'] < 0.5:
        return None
    ca, sa = to['u']
    hw, hd = to['L'] / 2, to['W'] / 2
    table = Polygon([world(to, a, c) for a, c in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd))])
    chairs = []
    for o, l in boxes:
        if l is tl or o['L'] > 0.7:
            continue
        cc = Point(o['c'])
        q = nearest_points(table.exterior, cc)[0]
        d = (q.x - cc.x, q.y - cc.y)
        if math.hypot(*d) < 1e-3:
            d = (to['c'][0] - cc.x, to['c'][1] - cc.y)
        chairs.append([R(cc.x), R(cc.y), R(ang(d), 4)])
    return dict(type='dining', c=RP(to['c']), w=R(to['L']), d=R(to['W']), a=R(ang(to['u']), 4), chairs=chairs)


def raster(o, pts, L, W, flip, step=0.02, scale=(1.0, 1.0)):
    """the points in o's frame (divided by scale: a block drawn smaller compared at full size)"""
    from scipy import ndimage
    nx, ny = int(L / step) + 1, int(W / step) + 1
    grid = np.zeros((ny, nx), bool)
    for p in pts:
        a, c = local(o, p)
        a, c = a / scale[0], c / scale[1]
        i, j = int((a * flip[0] + L / 2) / step), int((c * flip[1] + W / 2) / step)
        if 0 <= i < nx and 0 <= j < ny:
            grid[j, i] = True
    return ndimage.binary_dilation(grid, iterations=2)


_CANON = {}


def living(b, sheets):
    """the living-room set: the canonical pieces moved onto this instance, turned and mirrored the
    way the two drawings overlap best"""
    if not _CANON:
        key, i0 = LIVING_CANON
        cb = [x for x in B.sheet_blocks(sheets(key)) if x.i0 <= i0 <= x.i1][0]
        cb = max(split_runs([cb]), key=lambda x: len(x.items))
        _CANON.update(o=obb(cb.points()), pts=cb.points())
    co = _CANON['o']
    o = obb(b.points())
    L, W = co['L'], co['W']
    # (the drawings put the same set in at a smaller scale in the smaller living rooms - 0.8 on the
    # top floors of blocks Б and Г: compared and placed at its own scale)
    kx, ky = o['L'] / L, o['W'] / W
    if abs(kx - 1) < 0.03 and abs(ky - 1) < 0.03:
        kx = ky = 1.0
    ref = raster(co, _CANON['pts'], L, W, (1, 1))
    best = None
    for flip in ((1, 1), (-1, -1), (1, -1), (-1, 1)):
        g = raster(o, b.points(), L, W, flip, scale=(kx, ky))
        iou = (g & ref).sum() / max(1, (g | ref).sum())
        if best is None or iou > best[0]:
            best = (iou, flip)
    iou, (sx, sy) = best
    P = lambda a, c: world(o, a * sx * kx, c * sy * ky)
    D = lambda a, c: wdir(o, a * sx, c * sy)
    a0 = R(ang(o['u']), 4)
    out = []

    def rect(r):
        return P((r['x0'] + r['x1']) / 2, (r['y0'] + r['y1']) / 2), (r['x1'] - r['x0']) * kx, (r['y1'] - r['y0']) * ky
    c, w, d = rect(LIVING['rug'])
    out.append(dict(type='rug', c=RP(c), w=R(w), d=R(d), a=a0))
    s, ch = LIVING['sofa'], LIVING['chaise']
    boxes = []

    def add(part, x0, x1, y0, y1, z0, z1):
        cc = P((x0 + x1) / 2, (y0 + y1) / 2)
        boxes.append([R(cc[0]), R(cc[1]), R((x1 - x0) * kx), R((y1 - y0) * ky), z0, z1, a0, part])
    # the run's seats and the chaise, the back along the run, an arm at each end
    add('seat', s['x0'] + ARM, s['x1'] - ARM, s['y0'], s['y1'] - BACK, 0.0, 0.44)
    add('seat', ch['x0'], s['x1'] - ARM, ch['y0'], s['y0'], 0.0, 0.44)
    add('back', s['x0'] + ARM, s['x1'] - ARM, s['y1'] - BACK, s['y1'], 0.0, 0.82)
    add('arm', s['x0'], s['x0'] + ARM, s['y0'], s['y1'], 0.0, 0.62)
    add('arm', s['x1'] - ARM, s['x1'], ch['y0'], s['y1'], 0.0, 0.62)
    out.append(dict(type='sofa', boxes=boxes, f=R(ang(D(0, -1)), 4)))
    for cd in LIVING['chairs']:
        cc = P(*cd['c'])
        fd = D(math.cos(math.radians(cd['f'])), math.sin(math.radians(cd['f'])))
        out.append(dict(type='armchair', c=RP(cc), w=R(0.72 * (kx + ky) / 2), d=R(0.74 * (kx + ky) / 2), f=R(ang(fd), 4)))
    for t in LIVING['tables']:
        c, w, d = rect(t)
        out.append(dict(type='ctable', c=RP(c), w=R(w), d=R(d), a=a0, h=t['h']))
    for it in out:
        it['fit'] = R(iou, 2)
    return out


def classify(b, solid, sheets):
    c = b.counts
    if b.family == 'tan':
        return sanitary(b, solid)[0]
    if b.family == 'k06':
        o = obb(b.points())
        if o and 1.2 <= o['L'] <= 2.8 and 0.8 <= o['W'] <= 1.9 and c['k06'] >= 3:
            d = dining(b)
            return [d] if d else []
        return []
    o = obb(b.points())
    if o is None:
        return []
    L, W = o['L'], o['W']
    if c.get('fill', 0) >= 150 and c.get('k54', 0) >= 25:
        return living(b, sheets)
    if c.get('fill', 0) >= 4 and c.get('k72', 0) >= 60 and 2.2 <= L <= 3.1 and 1.5 <= W <= 2.4:
        return [bed(b, solid)]
    if c.get('k12', 0) >= 120 and 1.0 <= L <= 4.5 and 0.35 <= W <= 0.75:
        return [kitchen(b, solid)]
    if c.get('fill', 0) >= 1 and 6 <= c.get('k72', 0) <= 14 and 1.3 <= L <= 2.4 and W <= 0.4:
        axis, sign, _ = against_wall(o, solid, ['v'])
        return [wall_item('tv', o, axis, sign)]
    if 30 <= c.get('k12', 0) <= 70 and set(c) <= {'k12'} and 0.6 <= L <= 1.0 and 0.2 <= W <= 0.45:
        axis, sign, _ = against_wall(o, solid, ['v'])
        return [wall_item('ac', o, axis, sign)]
    return []


# ---------------------------------------------------------------------------- lifts

def lifts(sh, family):
    lines = []
    for d in sh.drawings:
        if E.R2(d.get('color')) == LIFT_RED:
            lines += [LineString(s) for s in sh.path_points(d) if len(s) >= 2]
    if not lines:
        return []
    U = unary_union([l.buffer(0.03) for l in lines])
    out = []
    for g in getattr(U, 'geoms', [U]):
        x0, y0, x1, y1 = g.bounds
        if min(x1 - x0, y1 - y0) < 1.2 or max(x1 - x0, y1 - y0) > 3.2:
            continue   # not a car (risers, stairs)
        mine = [l for l in lines if g.contains(l)]
        rings = [l for l in mine if len(l.coords) >= 4]
        car = max(rings, key=lambda l: l.envelope.area)
        o = obb(list(car.coords))
        # the counterweight: a thin box at the back of the car
        cw = None
        for l in mine:
            ex0, ey0, ex1, ey1 = l.bounds
            lo, hi = sorted((ex1 - ex0, ey1 - ey0))
            if lo < 0.2 and 0.4 < hi < 1.3 and len(l.coords) >= 4:
                cw = local(o, ((ex0 + ex1) / 2, (ey0 + ey1) / 2))
        if cw is None:
            continue
        if abs(cw[0]) / (o['L'] / 2) > abs(cw[1]) / (o['W'] / 2):
            f, w, d = wdir(o, -math.copysign(1, cw[0]), 0), o['W'], o['L']
        else:
            f, w, d = wdir(o, 0, -math.copysign(1, cw[1])), o['L'], o['W']
        q = min(LIFT_Q[family], key=lambda t: abs(t[0] - w))[1]
        out.append(dict(c=RP(o['c']), w=R(w), d=R(d), f=R(ang(f), 4), q=q))
    out.sort(key=lambda lf: (lf['c'][0], lf['c'][1]))
    return out


# ---------------------------------------------------------------------------- per sheet

_SHEETS = {}


def sheets(key):
    if key not in _SHEETS:
        _SHEETS[key] = E.Sheet(key)
    return _SHEETS[key]


def extract(sh, x):
    """the sheet's furniture and fittings (one list) and its lifts; x: the extraction (walls...)"""
    _SHEETS.setdefault(sh.key, sh)
    solid = unary_union([x['walls'], x['struct']] + list(x.get('windows', [])) + list(x.get('glazing', [])))
    region = x['enclosure'].buffer(2.0)
    runs = split_runs([b for b in B.sheet_blocks(sh, region) if len(b.items) >= 2])
    items = []
    for b in runs:
        if b.family == 'tan':
            got, used, n = sanitary(b, solid)
            items += got
            if n - used > 2:
                print('   sanitary run #%d: %d of %d strokes not read as a fitting' % (b.i0, n - used, n))
            continue
        items += classify(b, solid, sheets)
    # a block drawn twice over itself (it happens on these sheets) is one piece
    kept = []
    for it in items:
        if not any(k['type'] == it['type'] and math.dist(point_of(k), point_of(it)) < 0.05 for k in kept):
            kept.append(it)
    if len(kept) < len(items):
        print('   %d pieces drawn twice over' % (len(items) - len(kept)))
    items = kept
    family = 'A' if sh.key.startswith('A') else 'BG'
    lf = lifts(sh, family)
    kinds = {}
    for it in items:
        kinds[it['type']] = kinds.get(it['type'], 0) + 1
    print('  furniture:', ' '.join(f'{k} {v}' for k, v in sorted(kinds.items())), '| lifts', len(lf), [l['q'] for l in lf])
    return items, lf


def point_of(it):
    if 'c' in it:
        return it['c']
    bx = it['boxes']
    return [sum(b[0] for b in bx) / len(bx), sum(b[1] for b in bx) / len(bx)]


# ---------------------------------------------------------------------------- check picture

def draw(key, items, lifts_, enclosure, out, px=40):
    """the items over the sheet in plan orientation"""
    from PIL import Image, ImageDraw, ImageFont
    sh = sheets(key)
    info = E.SHEET_INFO[key]
    x0, y0, x1, y1 = enclosure.buffer(1.0).bounds
    W, H = int((x1 - x0) * px), int((y1 - y0) * px)
    dpi = 200
    k = dpi / 72
    pix = sh.pg.get_pixmap(dpi=dpi)
    sheet = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3]
    gx, gy = np.meshgrid(x0 + (np.arange(W) + 0.5) / px, y1 - (np.arange(H) + 0.5) / px)
    dx, dy = (gy, gx) if info['swap'] else (gx, -gy)
    U = np.clip(((sh.cx + dx * sh.s) * k).astype(int), 0, pix.width - 1)
    V = np.clip(((sh.cy + dy * sh.s) * k).astype(int), 0, pix.height - 1)
    im = Image.fromarray((sheet[V, U] * 0.5 + 255 * 0.5).astype(np.uint8))
    g = ImageDraw.Draw(im)
    f = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 10)
    T = lambda p: ((p[0] - x0) * px, (y1 - p[1]) * px)
    COL = dict(bed=(30, 90, 230), tv=(150, 70, 0), kitchen=(220, 0, 160), dining=(60, 60, 60), rug=(0, 160, 120), sofa=(0, 120, 0),
               armchair=(0, 170, 0), ctable=(140, 100, 0), toilet=(230, 30, 0), basin=(0, 150, 230), bath=(0, 70, 170), ac=(130, 0, 200))

    def rect(c, w, d, a, col, width=2):
        ca, sa = math.cos(a), math.sin(a)
        pts = [(c[0] + ca * x - sa * y, c[1] + sa * x + ca * y) for x, y in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2))]
        g.polygon([T(p) for p in pts], outline=col, width=width)

    def arrow(c, fa, col, L=0.45):
        e = (c[0] + math.cos(fa) * L, c[1] + math.sin(fa) * L)
        g.line([T(c), T(e)], fill=col, width=2)
        g.ellipse([T(e)[0] - 3, T(e)[1] - 3, T(e)[0] + 3, T(e)[1] + 3], fill=col)
    for it in items:
        t = it['type']
        col = COL.get(t, (255, 0, 0))
        if t in ('tv', 'kitchen', 'toilet', 'basin', 'bath', 'ac'):
            rect(it['c'], it['w'], it['d'], it['f'] - math.pi / 2, col)
            arrow(it['c'], it['f'], col, 0.3 + it['d'] / 2)
            fx = frame_x(it['f'])
            for key2, mark in (('sink', 'S'), ('hob', 'H')):
                if key2 in it:
                    p = (it['c'][0] + fx[0] * it[key2], it['c'][1] + fx[1] * it[key2])
                    g.text(T(p), mark, fill=col, font=f, anchor='mm')
            if 'tap' in it:
                p = (it['c'][0] + fx[0] * it['tap'] * it['w'] * 0.4, it['c'][1] + fx[1] * it['tap'] * it['w'] * 0.4)
                g.text(T(p), 'T', fill=col, font=f, anchor='mm')
        elif t == 'bed':
            rect(it['c'], it['w'], it['l'], it['f'] - math.pi / 2, col)
            arrow(it['c'], it['f'], col, 0.8)
            for s in it['stands']:
                rect(s[:2], s[2], s[3], it['f'] - math.pi / 2, col, 1)
        elif t in ('rug', 'ctable', 'dining'):
            rect(it['c'], it['w'], it['d'], it['a'], col, 1 if t == 'rug' else 2)
            for ch in it.get('chairs', []):
                rect(ch[:2], 0.42, 0.42, ch[2], col, 1)
                arrow(ch[:2], ch[2], col, 0.25)
        elif t == 'sofa':
            for bx in it['boxes']:
                rect(bx[:2], bx[2], bx[3], bx[6], col, 1)
            arrow(point_of(it), it['f'], col, 0.6)
        elif t == 'armchair':
            rect(it['c'], it['w'], it['d'], it['f'] - math.pi / 2, col)
            arrow(it['c'], it['f'], col)
        g.text(T(point_of(it)), t, fill=col, font=f)
    for lf in lifts_:
        rect(lf['c'], lf['w'], lf['d'], lf['f'] - math.pi / 2, (200, 0, 0), 3)
        arrow(lf['c'], lf['f'], (200, 0, 0), 1.2)
        g.text(T(lf['c']), f"Q={lf['q']}", fill=(200, 0, 0), font=f, anchor='mm')
    im.save(out)
    print(out, im.size)


if __name__ == '__main__':
    key, out = sys.argv[1], sys.argv[2]
    sh, x = E.build(key)
    _SHEETS[key] = sh
    items, lf = extract(sh, x)
    draw(key, items, lf, x['enclosure'], out)
