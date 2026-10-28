"""The five blocks, built floor by floor from the architect's plans (plans.json) in the look of the
marketing renders (00_Материалы_клиента/Рендеры).

Blocks Б, В, Г, Д (one typical plan, 64 x 26 m). The long faces read as three masses:
  - the centre section (|x| < 9.8 m) with a white stone pilaster up the middle of the face;
  - the stair-hall sections (9.8-19.3 m): the stair windows make a tall blue glazed strip;
  - the wings (beyond 19.3 m) to the ends.
Tan facing brick with punched windows; the small loggias (about 2 m2) behind dark perforated
screens, as dark ornamented strips from the base to the top; beige stone cornices at two levels;
a dark grey brick base above the shops, stepped: up to floor 6 on the wings, 5 in the centre;
the top floors white stone with fins, stepped as well (5 floors on the wings, 4 in the centre,
3 by the stairs), carried up past the roof as a crown.
Block A: a curtain wall, floor-to-ceiling glass with mullions and a thick white band at every
slab; dark strips where the walls between flats meet the glass; the corridor ends glazed full
height without bands; on floors 9-10 and 20-21 one recessed balcony per face (dark walls, glass
rail) where the plans draw terraces, the other terraces behind the glass as winter gardens; at the
south-west corner the bands of the lower floors run on past the corner in steps.

Every apartment floor is two objects (slab, walls) tagged with tower / floor / part, as the viewer
hides the floors above an opened one; floors that look the same share their meshes.
"""
import math

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from complex.geom import MeshBuilder, get_collection, make_object, resample, ring_coords
from complex.towers import pick_material

from .config import BLOCKS, FIRST_FLAT_FLOOR, SLAB, height, level, load_plans

REVEAL = 0.16    # windows sit this far behind the facade face
SILL = 0.85      # window sill above the floor level (as the viewer's interiors)
HEAD = 0.35      # wall between the window head and the slab above
SMALL_LOGGIA = 2.6  # m2: loggias up to this size are behind the perforated screens


def P(pts):
    return Polygon(pts).buffer(0)


def U(list_of_pts, grow=0.0):
    return unary_union([P(p).buffer(grow) for p in list_of_pts if len(p) >= 3])


# ----------------------------------------------------------------------------
# where things are on the brick blocks
# ----------------------------------------------------------------------------

SECTIONS = {'centre': [(-9.8, 9.8)], 'stair': [(-19.3, -9.8), (9.8, 19.3)], 'wing': [(-60, -19.3), (19.3, 60)]}


def section(x):
    return 'centre' if abs(x) < 9.8 else 'stair' if abs(x) <= 19.3 else 'wing'


def section_box(sec):
    return unary_union([box(a, -60, b, 60) for a, b in SECTIONS[sec]])


def white_from(block, sec):
    """first floor of the white stone top (render 1: four floors on the wings and by the stairs,
    five in the centre)"""
    N = block['floors']
    return {'wing': N - 3, 'centre': N - 4, 'stair': N - 3}[sec]


def dark_to(sec):
    """last floor of the dark brick base above the shops (render 1: stepped)"""
    return {'wing': 5, 'centre': 6, 'stair': 4}[sec]


def wall_of(block, f, sec):
    if f >= white_from(block, sec):
        return 'Stone white'
    if f <= dark_to(sec):
        return 'Brick dark'
    return 'Brick tan'


def cornice_floors(block):
    """beige stone cornices: at the foot of floors 11 and 17 (render 1)"""
    return (11, 17) if block['floors'] >= 22 else (10, 15)


# white stone pilasters from the shops to the roof where the centre section meets the stair
# sections, on both long faces (renders 1-3: "the white stripe")
PILASTERS = (-9.72, 9.72)
PIL_W, PIL_D = 0.7, 0.32


def mid_stripe(p):
    return False


def pilaster_spots(enc):
    """(x, y, outward sign) of every pilaster on the facade line of this plan"""
    out = []
    x0, y0, x1, y1 = enc.bounds
    for x in PILASTERS:
        line = LineString([(x, y0 - 1), (x, y1 + 1)]).intersection(enc)
        if line.is_empty:
            continue
        ys = [c[1] for g in getattr(line, 'geoms', [line]) for c in g.coords]
        out += [(x, max(ys), 1), (x, min(ys), -1)]
    return out


def pilasters(mb, enc, z0, z1):
    for x, y, sg in pilaster_spots(enc):
        mb.box(x, y + sg * (PIL_D / 2 - 0.04), z0, PIL_W, PIL_D, z1 - z0, 'Stone white', top=True, bottom=True)


def look_of(block, f):
    """everything about floor f that changes its facade (floors alike share their meshes)"""
    if block['style'] == 'glass':
        from . import tower_a
        return tower_a.look_of(f)
    from . import slab
    return slab.look_of(block, f)
    secs = ('centre', 'stair', 'wing')
    return (tuple(wall_of(block, f, s) for s in secs), f in cornice_floors(block),
            tuple(f == white_from(block, s) for s in secs), tuple(f == dark_to(s) + 1 for s in secs))


# ----------------------------------------------------------------------------
# the glass tower
# ----------------------------------------------------------------------------

# the bands of the lower floors run on past the corners in steps (renders 1 and 2): floor -> metres
# past the south-west corner (south face's bands) and past the north-west corner (west face's)
STAGGER = {3: (1.2, 2.6), 4: (3.4, 0.8), 5: (0.6, 3.8), 6: (2.4, 1.6), 7: (4.6, 0.5), 8: (1.6, 3.0),
           10: (3.0, 2.0), 11: (0.9, 4.2), 12: (2.2, 1.1), 13: (0.0, 2.6)}


_TYP = {}


def typical_A():
    if 'A' not in _TYP:
        _TYP['A'] = load_plans()['A']
    return _TYP['A']


def tower_outline(plan):
    """The curtain wall of block A: a plain square just outside the plan's outer walls (the facade
    line of the drawing has small jogs that the glass runs straight past)."""
    x0, y0, x1, y1 = P(plan['enclosure']).buffer(-0.8, join_style='mitre').buffer(0.8, join_style='mitre').bounds
    return box(x0 - 0.12, y0 - 0.12, x1 + 0.12, y1 + 0.12)


def glazed_column(plan, enc):
    """the band-less glass column of block A: where the stairs and the corridors reach the facade"""
    x0, y0, x1, y1 = enc.bounds
    com = unary_union([P(c) for c in plan['common'] if P(c).distance(enc.exterior) < 0.8])
    if com.is_empty:
        return Polygon()
    cy0, cy1 = com.bounds[1], com.bounds[3]
    return box(x0 - 1.0, cy0 - 0.2, x0 + 0.8, cy1 + 0.2)


def recess_group(f):
    return 1 if f in (9, 10) else 2 if f in (20, 21) else 0


def recess_terraces(plan, group):
    """terraces that stay open as recessed balconies: one per face, in staggered bays"""
    if not group:
        return []
    out = []
    for a in plan['apartments']:
        for r in a['balconies'] + a['rooms']:
            if r['kind'] != 'terrace' or not 6.0 < r['area'] < 12.0:
                continue
            c = P(r['poly']).centroid
            on_y = abs(c.y) > abs(c.x)
            along = c.x if on_y else c.y  # position along its face
            # (render 4: one recessed bay per face, the bays of the two groups staggered)
            if (group == 1 and -12.5 < along < -5.5) or (group == 2 and 5.5 < along < 12.5):
                out.append(P(r['poly']))
    return out


# ----------------------------------------------------------------------------
# facade of one apartment floor
# ----------------------------------------------------------------------------

def classify(enc, plan, f, block, step=0.3):
    """Sample the facade line and tell what each piece is."""
    glass_tower = block['style'] == 'glass'
    rooms = [r for a in plan['apartments'] for r in a['rooms'] + a['balconies']]
    small = U([r['poly'] for r in rooms if r['kind'] == 'loggia' and r['area'] <= SMALL_LOGGIA])
    common = U(plan['common'])
    wins = U(plan['windows'] + plan['glazing'], 0.0)
    solid = U(plan['walls'] + plan['struct'], 0.0)
    if glass_tower:
        # the dark mullion strips (where walls between flats meet the glass) follow the typical
        # floor on every floor, so they run straight up the tower
        typ = typical_A()
        wins = U(typ['windows'] + typ['glazing'], 0.0)
        solid = U(typ['walls'] + typ['struct'], 0.0)
    recess = unary_union(recess_terraces(plan, recess_group(f))) if glass_tower else Polygon()

    air = U([r['poly'] for r in rooms if r['kind'] == 'terrace']) if not glass_tower else recess
    pts = resample(ring_coords(enc), step)
    n = len(pts)
    cls = []
    ring_ccw = enc.exterior.is_ccw

    def behind(a, b, geom, depth=0.75):
        """is geom straight behind this piece of the facade (within depth, not just near it)?"""
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1e-9
        nx, ny = (dy / L, -dx / L) if ring_ccw else (-dy / L, dx / L)  # outward
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        probe = LineString([(mx + nx * 0.05, my + ny * 0.05), (mx - nx * depth, my - ny * depth)])
        return probe.intersects(geom)
    # the stair halls' tall glazing: 3.2 m in the middle of each stair window, dark screens either
    # side (render 1: dark - blue - dark)
    stair_wins = unary_union([P(w).buffer(0.3) for w in plan['windows'] if P(w).distance(common) < 0.5])
    glass_boxes = []
    for w in getattr(stair_wins, 'geoms', [stair_wins]):
        if w.is_empty:
            continue
        x0_, y0_, x1_, y1_ = w.bounds
        cx_, cy_ = (x0_ + x1_) / 2, (y0_ + y1_) / 2
        if x1_ - x0_ > y1_ - y0_:
            glass_boxes.append(box(cx_ - 1.6, y0_ - 1, cx_ + 1.6, y1_ + 1))
        else:
            glass_boxes.append(box(x0_ - 1, cy_ - 1.6, x1_ + 1, cy_ + 1.6))
    stair_glass = unary_union(glass_boxes) if glass_boxes else Polygon()
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        m = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if glass_tower:
            if not recess.is_empty and recess.distance(m) < 0.3:
                c = 'rail'
            elif common.distance(m) < 0.35:
                c = 'cglaze'
            elif solid.distance(m) < 0.25 and wins.distance(m) > 0.3:
                c = 'wallrun'
            else:
                c = 'glaze'
        else:
            on_win = behind(a, b, wins)
            if small.distance(m) < 0.1:
                c = 'screen'
            elif on_win and common.distance(m) < 0.5:
                c = 'stair' if stair_glass.contains(m) else 'screen'
            elif not air.is_empty and air.distance(m) < 0.3 and not on_win and solid.distance(m) > 0.12:
                c = 'rail'
            elif on_win:
                c = 'win'
            else:
                c = 'wall'
            if c == 'wall' and abs(m.x) < 0.6 and abs(m.y) > 8:
                c = 'pil'
        cls.append(c)
    if glass_tower:
        # short runs of wall along the glass are the walls between flats: dark strips; long runs
        # (columns, the walls of rooms along the facade) stay glass, the curtain wall runs past them
        i = 0
        while i < n:
            if cls[i] != 'wallrun':
                i += 1
                continue
            j = i
            while j < n and cls[j] == 'wallrun':
                j += 1
            kind = 'mull' if (j - i) * step <= 0.75 else 'glaze'
            for k in range(i, j):
                cls[k] = kind
            i = j
    # single stray samples (a 30 cm piece of something between two of another kind)
    for i in range(n):
        if cls[i - 1] == cls[(i + 1) % n] != cls[i] and cls[i] not in ('glaze', 'mull'):
            cls[i] = cls[i - 1]
    return pts, cls, dict(air=air, recess=recess, common=common)


def facade_floor(mb, enc, plan, f, block, h):
    """Walls, windows and glazing along the facade line of one floor (z = 0 at the floor level)."""
    glass_tower = block['style'] == 'glass'
    pts, cls, extra = classify(enc, plan, f, block)
    P_ = np.array(pts, float)
    n = len(P_)
    seg = np.roll(P_, -1, axis=0) - P_
    L = np.linalg.norm(seg, axis=1)
    us = np.concatenate([[0.0], np.cumsum(L)])
    t = seg / np.maximum(L, 1e-9)[:, None]
    out_seg = np.stack([t[:, 1], -t[:, 0]], axis=1)
    out_v = out_seg + np.roll(out_seg, 1, axis=0)
    out_v /= np.maximum(np.linalg.norm(out_v, axis=1), 1e-9)[:, None]
    inner = P_ - out_v * REVEAL
    T = lambda q: (float(q[0]), float(q[1]))
    frame = 'Frame dark' if glass_tower else 'Frame light'
    run = 0.0
    for i in range(n):
        j = (i + 1) % n
        a, b, c, u, l = T(P_[i]), T(P_[j]), cls[i], float(us[i]), float(L[i])
        rot = math.atan2(t[i][1], t[i][0])
        mid = (P_[i] + P_[j]) / 2
        wall = 'White band' if glass_tower else 'Stone white' if mid_stripe(mid) else wall_of(block, f, section(mid[0]))
        if c == 'rail':
            run = 0.0
            continue
        if c in ('glaze', 'cglaze', 'mull'):
            # curtain wall: glass in the facade plane, mullions about every 1.25 m, a transom at 1 m
            q0, q1 = T(P_[i] - out_seg[i] * 0.04), T(P_[j] - out_seg[i] * 0.04)
            if c == 'mull':
                mb.quad_wall(q0, q1, 0.0, h, 'Frame dark', u0=u)
                continue
            mb.quad_wall(q0, q1, 0.0, h, 'Tower glass', u0=u)
            if cls[i - 1] != c or run > 1.2:
                q = P_[i] - out_seg[i] * 0.01
                mb.box(q[0], q[1], 0.0, 0.05, 0.1, h, 'Frame dark', rot=rot)
                run = 0.0
            run += l
            if c == 'glaze':
                mb.box(mid[0] - out_seg[i][0] * 0.01, mid[1] - out_seg[i][1] * 0.01, 1.0, l + 0.01, 0.07, 0.05, 'Frame dark', rot=rot)
            continue
        if c in ('wall', 'pil'):
            mb.quad_wall(a, b, 0.0, h, 'Stone white' if c == 'pil' else wall, u0=u)
            run = 0.0
            continue
        if c == 'screen':
            # perforated screen in front of a small loggia, framed in dark brick
            s0, s1 = T(P_[i] - out_seg[i] * 0.06), T(P_[j] - out_seg[i] * 0.06)
            mb.quad_wall(a, b, 0.0, 0.1, 'Stone dark', u0=u)
            mb.quad_wall(s0, s1, 0.1, h - 0.1, 'Screen dark', u0=u)
            mb.quad_wall(a, b, h - 0.1, h, 'Stone dark', u0=u)
            if cls[i - 1] != c:
                mb.quad_wall(a, s0, 0.0, h, 'Stone dark')
            if cls[j] != c:
                mb.quad_wall(s1, b, 0.0, h, 'Stone dark')
            run = 0.0
            continue
        # punched windows ('win') and the stair hall's tall glazing ('stair')
        lo, hi = (0.0, h) if c == 'stair' else (SILL, h - HEAD)
        glass = 'Stair glass' if c == 'stair' else 'Window glass'
        ret = 'Stone white' if c == 'stair' else wall
        ai, bi = T(inner[i]), T(inner[j])
        mb.quad_wall(a, b, 0.0, lo, ret, u0=u)
        mb.quad_wall(a, b, hi, h, ret, u0=u)
        mb.quad_wall(ai, bi, lo, hi, glass, u0=u)
        mb.face([(*a, lo), (*b, lo), (*bi, lo), (*ai, lo)], ret, [(u, 0), (u + l, 0), (u + l, REVEAL), (u, REVEAL)])
        mb.face([(*ai, hi), (*bi, hi), (*b, hi), (*a, hi)], ret, [(u, REVEAL), (u + l, REVEAL), (u + l, 0), (u, 0)])
        if cls[i - 1] != c:
            mb.quad_wall(a, ai, lo, hi, ret, u0=0.0)
        if cls[j] != c:
            mb.quad_wall(bi, b, lo, hi, ret, u0=0.0)
        im = (inner[i] + inner[j]) / 2
        mb.box(im[0], im[1], lo, l + 0.01, 0.08, 0.06, frame, rot=rot)
        mb.box(im[0], im[1], hi - 0.06, l + 0.01, 0.08, 0.06, frame, rot=rot)
        if c == 'win':
            ds = mid + out_seg[i] * ((0.05 - REVEAL) / 2)
            mb.box(ds[0], ds[1], lo - 0.03, l + 0.01, REVEAL + 0.05, 0.03, 'Metal', rot=rot)
        else:
            mb.box(im[0], im[1], 1.05, l + 0.01, 0.07, 0.05, 'Frame dark', rot=rot)
        step = 0.9 if c == 'stair' else 0.75
        if cls[i - 1] != c or run > step:
            q = inner[i] + t[i] * (0.03 if cls[i - 1] != c else 0.0)
            mb.box(q[0], q[1], lo, 0.06, 0.08, hi - lo, 'Frame dark' if c == 'stair' else frame, rot=rot)
            run = 0.0
        run += l
        if cls[j] != c:
            q = inner[j] - t[i] * 0.03
            mb.box(q[0], q[1], lo, 0.06, 0.08, hi - lo, 'Frame dark' if c == 'stair' else frame, rot=rot)
    if not glass_tower:
        # white stone fins on the piers of the white top floors, a pilaster up the middle
        for k in range(n):
            mid = (P_[k] + P_[(k + 1) % n]) / 2
            if cls[k] == 'wall' and cls[k - 1] == 'win' and wall_of(block, f, section(mid[0])) == 'Stone white':
                q = P_[k] + out_seg[k] * 0.16 + t[k] * 0.12
                mb.box(q[0], q[1], 0.0, 0.24, 0.32, h, 'Stone white', rot=math.atan2(t[k][1], t[k][0]))
            if False and cls[k] == 'pil' and cls[k - 1] != 'pil':
                j = k
                while cls[(j + 1) % n] == 'pil':
                    j += 1
                a0, a1 = P_[k], P_[(j + 1) % n]
                m = (a0 + a1) / 2 + out_seg[k] * 0.09
                mb.box(m[0], m[1], 0.0, float(np.linalg.norm(a1 - a0)) + 0.2, 0.18, h, 'Stone white', rot=math.atan2(t[k][1], t[k][0]))
    return pts, cls, extra


def inner_openings(mb, plan, h, opened, wall_mat, glass_mat, glass_tower):
    """Behind open balconies and terraces the room fronts are inside the facade line: the plan's
    walls, windows and glazing there are built as they are (seen across the balcony)."""
    if not opened:
        return
    zone = unary_union([o.buffer(0.7) for o in opened])
    ring = P(plan['enclosure']).exterior.buffer(0.35)
    for w in plan['walls'] + plan['struct']:
        g = P(w)
        if g.intersects(zone) and not ring.contains(g):
            mb.prism(g.intersection(zone), 0.0, h, wall_mat, wall_mat)
    for lst, full in ((plan['windows'], False), (plan['glazing'], True)):
        for w in lst:
            g = P(w)
            if not g.intersects(zone) or ring.contains(g.centroid):
                continue
            core = g.buffer(-0.04) if not g.buffer(-0.04).is_empty else g
            if full or glass_tower:
                mb.prism(g, 0.0, 0.06, 'Frame dark', 'Frame dark')
                mb.prism(core, 0.06, h - 0.05, glass_mat)
                mb.prism(g, h - 0.12, h, 'Frame dark', 'Frame dark')
            else:
                mb.prism(g, 0.0, SILL, wall_mat, wall_mat)
                mb.prism(core, SILL, h - HEAD, glass_mat)
                mb.prism(g, h - HEAD, h, wall_mat, wall_mat)


def rails(mb, enc, air, z, white=True):
    """Glass rails on the open edges of balconies and terraces."""
    if air.is_empty:
        return
    edge = enc.exterior.intersection(air.buffer(0.35))
    lines = [edge] if edge.geom_type in ('LineString', 'LinearRing') else list(getattr(edge, 'geoms', []))
    for l in lines:
        if l.geom_type != 'LineString' or l.length < 0.4:
            continue
        cs = list(l.coords)
        mb.tube(cs, [z] * len(cs), [z + 0.12] * len(cs), 0.18, 'Stone white' if white else 'Frame dark')
        mb.ribbon(cs, z + 0.12, z + 1.1, 'Railing glass', double=True)
        mb.tube(cs, [z + 1.08] * len(cs), [z + 1.13] * len(cs), 0.06, 'Frame dark')


# ----------------------------------------------------------------------------
# meshes of one floor
# ----------------------------------------------------------------------------

def floor_meshes(block, plan, f, mats, name):
    """(slab mesh, walls mesh) of floor f, z = 0 at its floor level."""
    if block['style'] == 'glass':
        from . import tower_a
        return tower_a.floor_meshes(block, plan, f, mats, name, MeshBuilder)
    from . import slab
    return slab.floor_meshes(block, plan, f, mats, name, MeshBuilder)
    h = height(f, block)
    glass_tower = False
    enc = tower_outline(plan) if glass_tower else P(plan['enclosure'])
    mb = MeshBuilder()
    if glass_tower:
        # the floor, then the white band round it, standing 30 cm proud of the glass, broken where
        # the corridor ends are glazed full height
        mb.prism(enc.buffer(-0.06, join_style='mitre'), -0.25, SLAB, 'White band', 'Shop floor', 'White band')
        x0, y0, x1, y1 = enc.bounds
        ring = enc.buffer(0.34, join_style='mitre').difference(enc.buffer(-0.06, join_style='mitre'))
        # white bands on the west and the south face only; the north and east faces are all glass,
        # a slim dark line at each slab
        # white bands on all four faces (renders 1, 2, 4), broken by the glazed column at the stair
        # and corridor end of the west face, which is glass from bottom to top
        cuts = glazed_column(plan, enc)
        band = ring.difference(cuts)
        mb.prism(band, -0.42, 0.45, 'White band', 'White band', 'White band')
        line = enc.buffer(0.06, join_style='mitre').difference(enc.buffer(-0.06, join_style='mitre')).intersection(cuts)
        mb.prism(line, -0.06, 0.05, 'Frame dark', 'Frame dark', 'Frame dark')
        if f in STAGGER:
            ls, lw = STAGGER[f]
            if ls:
                mb.prism(box(x0 - 0.34 - ls, y0 - 0.34, x0 - 0.3, y0 + 0.06), -0.42, 0.45, 'White band', 'White band', 'White band')
            if lw:
                mb.prism(box(x0 - 0.34, y1 + 0.3, x0 + 0.06, y1 + 0.34 + lw), -0.42, 0.45, 'White band', 'White band', 'White band')
    else:
        mb.prism(enc.buffer(-0.08, join_style='mitre'), -0.2, SLAB, 'Stone white', 'Shop floor', 'Stone white')
        ring = enc.buffer(0.16, join_style='mitre').difference(enc.buffer(-0.05, join_style='mitre'))
        for x, y, sg in pilaster_spots(enc):  # the white pilasters run through the bands
            ring = ring.difference(box(x - PIL_W / 2, y - 0.6, x + PIL_W / 2, y + 0.6))
        if f in cornice_floors(block) or f == dark_to('wing') + 1:
            tan = unary_union([section_box(s) for s in SECTIONS if wall_of(block, f, s) == 'Brick tan'])
            mb.prism(ring.buffer(0.08, join_style='mitre').intersection(tan), -0.25, 0.3, 'Stone beige', 'Stone beige', 'Stone beige')
            mb.prism(ring.buffer(0.14, join_style='mitre').intersection(tan), 0.3, 0.42, 'Stone beige', 'Stone beige', 'Stone beige')
        for s in SECTIONS:
            if f == white_from(block, s):
                mb.prism(ring.buffer(0.04).intersection(section_box(s)), -0.3, 0.3, 'Stone white', 'Stone white', 'Stone white')
            elif f == dark_to(s) + 1 and dark_to(s) > 2:
                mb.prism(ring.intersection(section_box(s)), -0.25, -0.05, 'Stone dark', 'Stone dark', 'Stone dark')
    slab_mesh = mb.to_mesh(f'{name} slab', mats)
    mb = MeshBuilder()
    pts, cls, extra = facade_floor(mb, enc, plan, f, block, h)
    if glass_tower:
        inner_openings(mb, plan, h, recess_terraces(plan, recess_group(f)), 'Frame dark', 'Window glass', True)
        rails(mb, enc, extra['recess'], SLAB, white=True)
    else:
        rooms = [r for a in plan['apartments'] for r in a['rooms'] + a['balconies']]
        terr = [P(r['poly']) for r in rooms if r['kind'] == 'terrace']
        inner_openings(mb, plan, h, terr, 'Stone white', 'Window glass', False)
        rails(mb, enc, extra['air'], SLAB)
        pilasters(mb, enc, -0.2, h)
    return slab_mesh, mb.to_mesh(f'{name} walls', mats)


# ----------------------------------------------------------------------------
# block
# ----------------------------------------------------------------------------

def frame(block):
    a = math.radians(block['rot'])
    cx, cy = block['centre']
    ca, sa = math.cos(a), math.sin(a)
    return a, (lambda x, y: (cx + ca * x - sa * y, cy + sa * x + ca * y))


def footprint(key, plans=None):
    """The block's outline on the site (typical floor's facade line), site metres."""
    plans = plans or load_plans()
    b = BLOCKS[key]
    plan = plans[b['plans'][FIRST_FLAT_FLOOR]]
    _, to_site = frame(b)
    return Polygon([to_site(x, y) for x, y in plan['enclosure']]).buffer(0)


def build_block(key, mats, root_col, plans, podium=None):
    """All floors of one block. Returns its record for the viewer (complex.json)."""
    from .podium import build_base
    from .roof import build_roof
    b = BLOCKS[key]
    col = get_collection(f'Block {key}', root_col)
    a, to_site = frame(b)
    cx, cy = b['centre']

    def put(ob, z=0.0):
        ob.location = (cx, cy, z)
        ob.rotation_euler = (0, 0, a)
        return ob

    typical = plans[b['plans'][FIRST_FLAT_FLOOR]]
    # shops on floors 1-2 (and the podium round the block)
    build_base(key, b, typical, mats, col, put, podium)

    cache = {}
    floors = []
    pick_col = get_collection(f'Picking {key}', col) if b['sales'] else None
    for f in range(FIRST_FLAT_FLOOR, b['floors'] + 1):
        pk = b['plans'][f]
        z, h = level(f, b), height(f, b)
        ck = (pk, look_of(b, f))
        if ck not in cache:
            cache[ck] = floor_meshes(b, plans[pk], f, mats, f'{key} {pk} {len(cache)}')
        sm, wm = cache[ck]
        for part, me in (('slab', sm), ('walls', wm)):
            ob = put(make_object(f"{key} {'floor' if part == 'slab' else 'walls'} {f:02d}", me, col), z)
            ob['tower'], ob['floor'], ob['part'] = key, f, part
        if b['sales']:
            for i, apt in enumerate(plans[pk]['apartments']):
                mb = MeshBuilder()
                mb.prism(P(apt['outline']).buffer(0.2, join_style='mitre').simplify(0.1), -0.15, h - 0.1, 'Pick', 'Pick', 'Pick')
                nm = f'pick {key} {f:02d} {i}'
                ob = put(make_object(nm, mb.to_mesh(nm, {'Pick': pick_material()}), pick_col), z + SLAB)
                ob['tower'], ob['floor'], ob['unit'], ob['pick'] = key, f, i, 1
                ob.hide_render = True
        floors.append(dict(floor=f, z=round(z, 3), h=round(h, 3), plan=pk))

    top = plans[b['plans'][b['floors']]]
    zr = level(b['floors'] + 1, b)
    mb = MeshBuilder()
    build_roof(mb, b, top, zr)
    ob = put(make_object(f'{key} roof', mb.to_mesh(f'{key} roof', mats), col))
    ob['tower'], ob['part'] = key, 'roof'
    return dict(key=key, label=b['label'], tj=b['tj'], centre=list(b['centre']), rot=round(b['rot'], 3), plan_centre=[0.0, 0.0],
                slab=SLAB, floors=floors if b['sales'] else [], levels=b['floors'], top=round(zr, 3), sales=b['sales'],
                outline=[[round(x, 2), round(y, 2)] for x, y in footprint(key, plans).exterior.coords])
