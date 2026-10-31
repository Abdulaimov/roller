"""The three residential blocks, floor by floor from the sales book's plans (blender/rp/plans.json,
tools/rp/extract.py), dressed in the look of the client's renders (00_Материалы_клиента/Рендеры) and
the developer's model (фото макета):

  - the plan's walls and concrete stand as drawn, each outer side in the finish of the face it is
    on (SKIN): on the street faces silver cladding, and every window glass from floor to floor in a
    dark grid, the glass running on over the slabs - from the street the towers read grey and
    mirror-like, the windows lost in the glass (renders 1-4); the faces towards block Б graphite
    with punched windows; the yard faces light with punched windows under a graphite top (render 5);
  - silver-white pilasters where the sheets draw them (the grey outlines on the facades), graphite in
    the yard faces' graphite top; a band at every slab round the loggias and on the yard and
    graphite faces, none across the street faces;
  - balconies: white slab edge, glass railing; their back walls warm wood (the lit loggias of the
    night renders); on Б's face to кӯчаи Ҳусейнзода the balconies are glazed floor to ceiling (the
    big glass corner of renders 1 and 2);
  - the crown: a tall white frame with posts and a railing round the roof terrace, solar panels.

Every apartment floor is two objects (slab, walls) tagged tower / floor / part: the viewer hides the
floors above an opened one; floors that look the same share their meshes.
"""
import math
import random

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from complex.geom import MeshBuilder, ccw, get_collection, log_tree, make_object
from complex.towers import pick_material

from .config import BLOCKS, FIRST_FLAT_FLOOR, SLAB, height, level

# The finish of each face of a block, on the sheets' axes: +x faces кӯчаи Ҳусейнзода, +y кӯчаи
# Нарзиқулова (28.10.2026, the user on renders 1-4: «the house is all white, there it is grey,
# mirror-like; on block В you can hardly see a window»):
#   street - silver cladding, punched windows; the zones below on top of it;
#   dark   - graphite cladding, punched windows: А's and В's faces towards Б (renders 1, 4);
#   yard   - light cladding, punched windows (render 5).
SKIN = {
    'A': {'+x': 'street', '+y': 'dark', '-x': 'yard', '-y': 'yard'},
    'B': {'+x': 'street', '+y': 'street', '-x': 'yard', '-y': 'yard'},
    'V': {'+x': 'dark', '+y': 'street', '-x': 'yard', '-y': 'yard'},
}
# the yard faces' graphite top: floors under the crown (render 5: about five on А's yard face and
# seven on its south end, six on В's yard face; ten on В's west end, render 3 too)
DARK_TOP = {'A': {'-x': 5, '-y': 7}, 'B': {}, 'V': {'-y': 6, '-x': 10}}
CLAD = {'street': 'Facade silver', 'dark': 'Facade dark', 'yard': 'Facade white'}
# The faces' vertical zones, read bay by bay off renders 1-5 and the developer's model (photos
# IMG_4103-4108) against the sheets' windows and pilasters (30.10.2026, the user: «some parts of the
# house are dark, some light; where the windows are panoramic, where plain - exactly as the renders»).
# t: metres along the face of the block's typical plan (TYP), from its left end seen from outside.
#   glass - a curtain strip pilaster to pilaster, floor to floor, the slabs behind it: mirror glass in
#           a dark grid, the walls and windows in it hidden (the model's black strips, the renders'
#           blue-grey glass); fin: where the slim white double fin stands in it (the sheet's pilaster
#           there), up to FIN_STOP floors under the top
#   gold  - Б's wood «T» (render 4: warm wood; the model's is bronze) - bar: its top bar's span, over
#           the top typical floor; lilac - Б's fluted strip by the glass corner; slot - В's middle
#           channel between its two halves (grey panels); blank - graphite, no window (А's face to Б
#           by its corner on Ҳусейнзода, renders 1 and 4: a dark tiled panel - the sheets draw two
#           windows there)
TYP = {'A': 'A_typ', 'B': 'B_typ', 'V': 'V_typ'}
ZONES = {
    # А to кӯчаи Ҳусейнзода (photo 4103, renders 1, 4): a strip over the windows 0.9, 0.9, 1.5 with the
    # pilaster in it as the fin, the 1.5 window punched, two loggias, a window column, a strip over the
    # windows 1.7, 1.7; to the yard (render 5, photo 4106) a strip by the south-west corner
    'A': {'+x': [(2.94, 8.91, 'glass', 6.51), (24.34, 29.20, 'glass', 26.76)],
          '-x': [(25.92, 29.05, 'glass', None)],
          # (to Б: render 4 over Б's roof - blank tiles, the loggia's slot, the two long windows as four
          # tall ones, blank tiles to the yard corner; the sheets draw two more windows there)
          '+y': [(-1.0, 5.63, 'blank', None), (20.9, 31.6, 'blank', None)]},
    # Б (photos 4103-4105, renders 1, 2, 4, 6): on both street faces, mirrored about the corner: a narrow
    # strip, loggia, window, loggia, the T, loggia, a narrow strip, the fluted strip, the glass corner
    'B': {'+x': [(1.21, 3.50, 'glass', None), (12.85, 13.75, 'gold', (9.80, 16.80)),
                 (16.85, 18.55, 'glass', None), (18.55, 20.68, 'lilac', None)],
          '+y': [(9.76, 11.85, 'lilac', None), (11.85, 13.60, 'glass', None),
                 (16.70, 17.60, 'gold', (13.66, 20.66)), (27.25, 29.21, 'glass', None)]},
    # В to кӯчаи Нарзиқулова (photo 4104, render 3): two halves round the middle channel, each a narrow
    # strip, two loggias, a wide strip with the fin, two loggias, a narrow strip; the west end (photo
    # 4106, render 3) a wide strip with the fin in its middle
    'V': {'+y': [(2.60, 5.05, 'glass', None), (12.55, 17.37, 'glass', 14.96), (25.74, 27.55, 'glass', None),
                 (27.55, 31.85, 'slot', None), (31.85, 33.66, 'glass', None), (42.03, 46.84, 'glass', 44.43),
                 (54.40, 57.50, 'glass', None)],
          '-x': [(9.95, 21.60, 'glass', 15.78)]},
}
FIN_STOP = 4         # the fins end this many floors under the top (photos 4103, 4104; render 3)
REF = {}             # the typical plans' bounds, by block (build_block sets it)
ZONE_CLAD = {'glass': 'Facade dark', 'gold': 'Facade silver', 'lilac': 'Facade dark', 'slot': 'Facade silver', 'blank': 'Facade dark'}
INNER = 'Facade white'   # the walls' sides indoors (seen only in the cut-away views)
SIDES = {'+x': (1.0, 0.0), '-x': (-1.0, 0.0), '+y': (0.0, 1.0), '-y': (0.0, -1.0)}
SILL, HEAD = 0.45, 0.35
PANORAMIC = 2.4   # m: windows this long on the sheets are the model's dark curtain-glass strips
GLASS_FACE = {'B': lambda x, y: x > 12.5}   # Б: the balconies on the east face are glazed full height
SOLAR = {'A': 4, 'B': 2, 'V': 9}
# plants on the balconies, where the renders have them: (block, floor) -> [(face, t, kind)] - render 6,
# Б's balcony right of the T on кӯчаи Ҳусейнзода: a bush on the 4th floor, a small plant on the 3rd
PLANTS = {('B', 3): [('+x', 14.3, 'small')], ('B', 4): [('+x', 14.3, 'bush')]}   # PV arrays on the roof (two rows of panels each), counted on renders 4 and 5


def P(p):
    g = Polygon(p).buffer(0)
    return max(g.geoms, key=lambda q: q.area) if g.geom_type == 'MultiPolygon' else g


def U(polys, grow=0.0):
    return unary_union([P(p).buffer(grow, join_style='mitre') for p in polys if len(p) >= 3])


def parts(g):
    if g.is_empty:
        return []
    return [q for q in getattr(g, 'geoms', [g]) if q.geom_type == 'Polygon']


def outdoor_rooms(plan):
    return [P(r['poly']) for a in plan['apartments'] for r in a['rooms'] + a['balconies'] if r['kind'] in ('loggia', 'terrace')]


def axis(q):
    """long axis of a quad: (centre, u (along), v (across), length, thickness)"""
    r = q.minimum_rotated_rectangle
    c = list(r.exterior.coords)[:4]
    e1 = (c[1][0] - c[0][0], c[1][1] - c[0][1])
    e2 = (c[2][0] - c[1][0], c[2][1] - c[1][1])
    l1, l2 = math.hypot(*e1), math.hypot(*e2)
    if l1 < l2:
        e1, e2, l1, l2 = e2, e1, l2, l1
    u = (e1[0] / l1, e1[1] / l1)
    v = (-u[1], u[0])
    ct = r.centroid
    return (ct.x, ct.y), u, v, l1, l2


def pane(mb, c, u, v, L, t, off, z0, z1, glass, frame='Frame dark', mullion=1.5, fw=0.06, transom=None):
    """a glazed opening across a wall: glass at offset `off` across the wall, a frame round it,
    mullions about every `mullion` metres and a transom `transom` above the bottom"""
    cx, cy = c[0] + v[0] * off, c[1] + v[1] * off
    rot = math.atan2(u[1], u[0])
    mb.box(cx, cy, z0, L, 0.03, z1 - z0, glass, rot=rot)
    for zz in (z0, z1 - fw) + ((z0 + transom,) if transom else ()):
        mb.box(cx, cy, zz, L, 0.09, fw, frame, rot=rot)
    n = max(1, round(L / mullion))
    for k in range(n + 1):
        s = -L / 2 + L * k / n
        s = max(-L / 2 + fw / 2, min(L / 2 - fw / 2, s))
        mb.box(cx + u[0] * s, cy + u[1] * s, z0, fw, 0.09, z1 - z0, frame, rot=rot)


def facing(bounds, m, n):
    """the face of the block a surface at m looking along n is on: the nearest side of the block's
    box among those it does not turn its back on (so the walls of В's middle slot and of the
    setbacks go with the face they are cut into)"""
    x0, y0, x1, y1 = bounds
    d = {'+x': x1 - m[0], '-x': m[0] - x0, '+y': y1 - m[1], '-y': m[1] - y0}
    return min((s for s, (sx, sy) in SIDES.items() if n[0] * sx + n[1] * sy > -0.05), key=lambda s: d[s])


def along(key, face, m):
    """where the point m lies along a face, in the face's t (ZONES): from its left end seen from outside"""
    x0, y0, x1, y1 = REF[key]
    return {'+x': m[1] - y0, '-x': y1 - m[1], '+y': x1 - m[0], '-y': m[0] - x0}[face]


def at_t(key, face, t):
    """the coordinate along the face at its t (the other one: the face's line)"""
    x0, y0, x1, y1 = REF[key]
    return {'+x': y0 + t, '-x': y1 - t, '+y': x1 - t, '-y': x0 + t}[face]


def zone_at(key, face, m, margin=0.0):
    """the narrowest zone of that face the point m is in (margin m inside its ends), or None"""
    t = along(key, face, m)
    hits = [z for z in ZONES.get(key, {}).get(face, []) if z[0] + margin <= t <= z[1] - margin]
    return min(hits, key=lambda z: z[1] - z[0]) if hits else None


def skin_of(key, f, top_floor):
    """the finish of each face on floor f: SKIN, with the graphite top of the yard faces"""
    s = dict(SKIN[key])
    for face, n in DARK_TOP[key].items():
        if f > top_floor - n:
            s[face] = 'dark'
    return s


def clad_prism(mb, g, h, finish):
    """a wall or a column floor to ceiling, each side in the finish of what it looks onto
    (finish(midpoint, outward normal) -> material)"""
    g = ccw(g)
    for ring in [g.exterior] + list(g.interiors):
        c = list(ring.coords)[:-1]
        u = 0.0
        for a, b in zip(c, c[1:] + c[:1]):
            L = math.dist(a, b)
            if L < 1e-6:
                continue
            n = ((b[1] - a[1]) / L, -(b[0] - a[0]) / L)
            mb.quad_wall(a, b, 0.0, h, finish(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), n), u0=u)
            u += L
    mb.polygon_face(g, h, INNER, up=True)


def outer_edges(g, outside):
    """the edges of a strip (a balcony's parapet or glass) that face the open air, as (a, b) lines
    a few centimetres in from it: an L-shaped corner balcony has two (its long axis ran diagonally
    across the corner, a railing through the air - block В, 28.10.2026)"""
    out = []
    pts = list(g.exterior.coords)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 0.25:
            continue
        nx, ny = (y1 - y0) / L, -(x1 - x0) / L
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        if g.contains(Point(mx + nx * 0.01, my + ny * 0.01)):
            nx, ny = -nx, -ny
        if outside.contains(Point(mx + nx * 0.15, my + ny * 0.15)):
            out.append(((x0 - nx * 0.05, y0 - ny * 0.05), (x1 - nx * 0.05, y1 - ny * 0.05)))
    return out


def loggia_rail(mb, a, b, curb='White band'):
    """a balcony's railing as the renders draw it (renders 1, 3, 6): light frosted glass on a thin
    white curb at the slab's edge, a slim dark handrail along its top, dark posts at its ends - the
    loggias read white and light with the wood behind, not as brown slots"""
    L = math.dist(a, b)
    if L < 0.1:
        return
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    rot = math.atan2(u[1], u[0])
    c = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    mb.box(c[0], c[1], 0.0, L, 0.12, SLAB + 0.06, curb, rot=rot)
    mb.box(c[0], c[1], SLAB + 0.04, L, 0.02, 1.02, 'Railing glass', rot=rot)
    mb.box(c[0], c[1], SLAB + 1.04, L + 0.02, 0.06, 0.05, 'Frame dark', rot=rot, bottom=True)
    for e in (-L / 2 + 0.03, L / 2 - 0.03):
        mb.box(c[0] + u[0] * e, c[1] + u[1] * e, SLAB + 0.04, 0.05, 0.05, 1.02, 'Frame dark', rot=rot)


def potted_cypress(mb, x, y, z, h, rnd):
    """a slim cypress in a dark square planter (the roof terraces of renders 1-5)"""
    mb.box(x, y, z, 0.55, 0.55, 0.5, 'Frame dark')
    r = rnd.uniform(0.26, 0.32)
    mb.blob(x, y, z + 0.45 + h * 0.42, r, r, h * 0.45, 'Shrub', subdiv=1, jitter=0.06, rnd=rnd)
    mb.blob(x, y, z + 0.45 + h * 0.8, r * 0.6, r * 0.6, h * 0.17, 'Shrub', subdiv=1, jitter=0.05, rnd=rnd)


def potted_tree(mb, x, y, z, rnd, h=2.3):
    """a small round-headed tree in a white pot (Б's corner terrace, render 4)"""
    mb.prism(Point(x, y).buffer(0.32, quad_segs=4), z, z + 0.55, 'Stone white', 'Mulch')
    mb.box(x, y, z + 0.5, 0.07, 0.07, h - 0.9, 'Trunk')
    mb.blob(x, y, z + h - 0.35, 0.55, 0.55, 0.5, 'Leaves light', subdiv=2, jitter=0.07, rnd=rnd)


def solar_arrays(mb, free, z, n, cols=4, pw=1.0, pl=1.7, tilt=18):
    """n arrays of two tilted rows of `cols` panels, spread over the free roof (renders 4, 5: groups
    round the plant rooms and along the parapet, not a field)"""
    if n <= 0 or free.is_empty:
        return
    W, D = cols * (pw + 0.05), 2 * pl + 0.7
    x0, y0, x1, y1 = free.bounds
    cands = []
    y = y0 + D / 2
    while y <= y1 - D / 2:
        x = x0 + W / 2
        while x <= x1 - W / 2:
            if free.contains(box(x - W / 2, y - D / 2, x + W / 2, y + D / 2)):
                cands.append((x, y))
            x += 0.5
        y += 0.5
    if not cands:
        return
    # the first next to the parapet, then each as far from the others as it can be
    edge = free.exterior
    picks = [min(cands, key=lambda c: edge.distance(Point(c)))]
    while len(picks) < n:
        far = max(cands, key=lambda c: min(math.dist(c, p) for p in picks))
        if min(math.dist(far, p) for p in picks) < max(W, D) + 0.6:
            break
        picks.append(far)
    rise = pl * math.sin(math.radians(tilt))
    for (cx, cy) in picks:
        for r in (0, 1):
            ya = cy - D / 2 + r * (pl + 0.7)
            for k in range(cols):
                xa = cx - W / 2 + k * (pw + 0.05)
                mb.face([(xa, ya, z + 0.3), (xa + pw, ya, z + 0.3), (xa + pw, ya + pl, z + 0.3 + rise), (xa, ya + pl, z + 0.3 + rise)], 'Solar panel')
            for yy, hh in ((ya + 0.05, 0.3), (ya + pl - 0.05, 0.3 + rise)):
                mb.box(cx, yy, z, W, 0.05, hh, 'Frame dark')


def face_line(enc, face, a, b):
    """the face's outermost line over the stretch a..b along it (the outline steps in and out)"""
    x0, y0, x1, y1 = enc.bounds
    lo, hi = min(a, b), max(a, b)
    if face in ('+x', '-x'):
        q = enc.intersection(box(x0 - 5, lo, x1 + 5, hi))
    else:
        q = enc.intersection(box(lo, y0 - 5, hi, y1 + 5))
    if q.is_empty:
        return None
    qx0, qy0, qx1, qy1 = q.bounds
    return {'+x': qx1, '-x': qx0, '+y': qy1, '-y': qy0}[face]


def zone_dress(mb, key, plan, h, fin_on, tbar):
    """what the zones put on the face (ZONES): the curtain strips' mirror glass in its dark grid
    floor to floor (the slab's edge behind it, so the strips run on unbroken), the fins, Б's T and
    its fluted strip"""
    enc = P(plan['enclosure'])
    z0, z1 = -0.32, h - 0.32
    for face, zs in ZONES.get(key, {}).items():
        sx, sy = SIDES[face]

        def at(c, o):
            # a point o metres out from the face line, at c along the face
            return (line + sx * o, c) if face in ('+x', '-x') else (c, line + sy * o)

        def bar(c, w, o, d, za, zb, mat):
            # a box w along the face, d deep, its middle o out from the face line
            p = at(c, o)
            if face in ('+x', '-x'):
                mb.box(p[0], p[1], za, d, w, zb - za, mat)
            else:
                mb.box(p[0], p[1], za, w, d, zb - za, mat)
        for t0, t1, kind, extra in zs:
            a, b = at_t(key, face, t0), at_t(key, face, t1)
            line = face_line(enc, face, a, b)
            if line is None:
                continue
            w, mid = abs(b - a), (a + b) / 2
            if kind == 'glass':
                bar(mid, w, 0.05, 0.03, z0, z1, 'Strip glass')
                n = max(1, round(w / 1.05))
                for k in range(n + 1):
                    c = min(a, b) + w * k / n
                    bar(c, 0.06, 0.08, 0.1, z0, z1, 'Frame dark')
                for za, zb in ((z0, z0 + 0.07), (0.98, 1.03)):
                    bar(mid, w, 0.08, 0.1, za, zb, 'Frame dark')
                if extra is not None and fin_on:
                    cf = at_t(key, face, extra)
                    for s in (-0.17, 0.17):
                        bar(cf + s, 0.12, 0.22, 0.28, z0, z1, 'Pilaster white')
            elif kind == 'gold':
                bar(mid, w, 0.17, 0.32, z0, z1, 'Strip wood')
                if tbar and extra:
                    ea, eb = at_t(key, face, extra[0]), at_t(key, face, extra[1])
                    bar((ea + eb) / 2, abs(eb - ea), 0.17, 0.32, h - 0.95, z1, 'Strip wood')
            elif kind == 'lilac':
                bar(mid, w, 0.02, 0.02, z0, z1, 'Facade dark')
                n = max(2, int(w / 0.16))
                for k in range(n + 1):
                    bar(min(a, b) + 0.03 + (w - 0.06) * k / n, 0.05, 0.17, 0.3, z0, z1, 'Fin lilac')


def facade_floor(mb, block, plan, h, skin, top=False, zones=True, fin_on=True, tbar=False):
    key = block['key']
    enc = P(plan['enclosure'])
    bounds = enc.bounds
    zone = (lambda face, m, margin=0.0: zone_at(key, face, m, margin)) if zones else (lambda *a, **k: None)
    outside = box(*enc.buffer(30).bounds).difference(enc)
    out_rooms = outdoor_rooms(plan)
    outdoor = unary_union(out_rooms) if out_rooms else Polygon()
    glass_face = GLASS_FACE.get(key, lambda x, y: False)
    rim = enc.exterior
    # recesses inside the sheet's outline that open onto it - no room, hall, stair, shaft or wall
    # in them (А's yard face: the end of the corridor and the stair, 2 m deep, a dark slot the
    # height of the block on render 5; Б's third floor: the corner under the glass): their walls
    # are outer walls, graphite
    used = unary_union([P(r['poly']) for a in plan['apartments'] for r in a['rooms'] + a['balconies']]
                       + [P(c) for c in plan['common']] + [P(lf['shaft']) for lf in plan.get('lifts', [])]
                       + [P(w) for w in plan['walls'] + plan['struct'] if len(w) >= 3])
    wells = [q for q in parts(enc.buffer(-0.05).difference(used.buffer(0.08))) if q.area > 3 and q.distance(rim) < 0.1]
    recess = unary_union([q.buffer(0.1, join_style='mitre') for q in wells]) if wells else Polygon()
    air = outside.union(outdoor).union(recess)
    # each loggia's open sides (their outward normals): the wall facing one is the loggia's back wall
    # - warm wood; its sides are the pilasters' flanks - white (renders 1, 6)
    opens = []
    for g in out_rooms:
        ns = []
        pts = list(ccw(g).exterior.coords)
        for a, b in zip(pts, pts[1:]):
            L = math.dist(a, b)
            if L < 0.3:
                continue
            n = ((b[1] - a[1]) / L, -(b[0] - a[0]) / L)
            if outside.contains(Point((a[0] + b[0]) / 2 + n[0] * 0.5, (a[1] + b[1]) / 2 + n[1] * 0.5)):
                ns.append(n)
        opens.append((g, ns))

    def rail(a, b):
        # (on the graphite faces the loggias' curbs are graphite too - render 4: no white there)
        L = math.dist(a, b)
        n = ((b[1] - a[1]) / L, -(b[0] - a[0]) / L) if L > 1e-6 else (1.0, 0.0)
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if not outside.contains(Point(m[0] + n[0] * 0.6, m[1] + n[1] * 0.6)):
            n = (-n[0], -n[1])
        f = facing(bounds, m, n)
        loggia_rail(mb, a, b, CLAD['dark'] if skin[f] == 'dark' else 'White band')

    def clad(face, m):
        z = zone(face, m)
        return ZONE_CLAD[z[2]] if z else CLAD[skin[face]]

    def finish(m, n):
        """what a wall's side at m looking along n is clad in"""
        p = Point(m[0] + n[0] * 0.15, m[1] + n[1] * 0.15)
        if outside.contains(p):
            return clad(facing(bounds, m, n), m)
        if recess.contains(p):
            return CLAD['dark']
        if not outdoor.is_empty and (outdoor.contains(p) or outdoor.distance(Point(m)) < 0.4):
            # the back walls of the loggias: warm wood (renders 1, 2, 4, 6); their sides white
            g, ns = min(opens, key=lambda o: o[0].distance(p))
            if not ns or any(n[0] * o[0] + n[1] * o[1] > 0.7 for o in ns):
                return 'Loggia beige'
            f = facing(bounds, (g.centroid.x, g.centroid.y), ns[0])
            return 'Pilaster white' if skin[f] == 'street' else CLAD[skin[f]]
        q = Point(m)
        if rim.distance(q) < 0.6:
            # a window's jamb, the reveal: the face's own finish
            e = rim.interpolate(rim.project(q))
            d = (e.x - m[0], e.y - m[1])
            k = math.hypot(*d) or 1.0
            return clad(facing(bounds, m, (d[0] / k, d[1] / k)), m)
        return INNER

    # walls and concrete as drawn, each side in its finish; nothing stands in a window's or a
    # glazing's opening (the sheets' window symbol - the frame and sill lines across the opening -
    # came out of the plans as thin walls there, floor to ceiling in front of the glass)
    # (the opening through the whole wall: the window's rectangle 5 cm deeper both ways - an outline
    # 1.3 cm thick ran across the glass of В's windows - but no wider, the piers keep their ends)
    def through(q):
        c, u, v, L, t = axis(P(q))
        a, b = L / 2 + 0.005, t / 2 + 0.05
        return Polygon([(c[0] + u[0] * su * a + v[0] * sv * b, c[1] + u[1] * su * a + v[1] * sv * b)
                        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    openings = unary_union([through(q) for q in plan['windows'] + plan['glazing'] if len(q) >= 3 and P(q).area > 0.004])
    for w in plan['walls'] + plan['struct']:
        g0 = P(w)
        if g0.area < 0.01:
            continue
        for g in parts(g0.difference(openings)):
            if g.area < 0.01:
                continue
            # (a sliver of the sheet's outline stroke along the facade or a loggia's open side, 2 cm
            # thick and metres long, is no wall: it stood floor to ceiling across loggias and in
            # front of Б's glass corner - V_typ had 24 by the loggias, 85 m in all)
            L = axis(g)[3]
            if L > 0.4 and g.area / L < 0.05 and (rim.distance(g) < 0.1 or (not outdoor.is_empty and outdoor.distance(g) < 0.1)):
                continue
            clad_prism(mb, g, h, finish)
    # the loggias' downlights: two round lamps in each loggia's ceiling, on in every render, day and
    # night (renders 1, 3, 4, 6); at night each throws a warm fan of light down the wood behind it
    for g, ns in opens:
        c, u, v, L, t = axis(g)
        k = 2 if L > 2.4 else 1
        o = ns[0] if ns else None
        # (nearer the open side: the lamps hang over the balcony, not by the door)
        fwd = (o[0] * t * 0.15, o[1] * t * 0.15) if o else (0.0, 0.0)
        for i in range(k):
            s = ((i + 0.5) / k - 0.5) * L * 0.6
            q = Point(c[0] + u[0] * s + fwd[0], c[1] + u[1] * s + fwd[1])
            mb.prism(q.buffer(0.09, quad_segs=3), h - 0.27, h - 0.25, 'Downlight', None, 'Downlight')
        if o is None:
            continue
        # the back wall: the loggia's side opposite the open one
        pts = list(ccw(g).exterior.coords)
        back = [(a, b) for a, b in zip(pts, pts[1:]) if math.dist(a, b) > 0.8
                and ((b[1] - a[1]) * o[0] - (b[0] - a[0]) * o[1]) / math.dist(a, b) < -0.7]
        if not back:
            continue
        a, b = max(back, key=lambda e: math.dist(*e))
        Lb = math.dist(a, b)
        ub = ((b[0] - a[0]) / Lb, (b[1] - a[1]) / Lb)
        for i in range(k):
            s0, s1 = Lb * i / k + 0.15, Lb * (i + 1) / k - 0.15
            pa = (a[0] + ub[0] * s0 + o[0] * 0.03, a[1] + ub[1] * s0 + o[1] * 0.03)
            pb = (a[0] + ub[0] * s1 + o[0] * 0.03, a[1] + ub[1] * s1 + o[1] * 0.03)
            # (the beam's UV: v 0 at the fixture - here at the top, falling to the rail)
            mb.face([(*pa, h - 0.3), (*pb, h - 0.3), (*pb, 0.9), (*pa, 0.9)], 'Night wash', [(0, 0), (1, 0), (1, 1), (0, 1)])
    # windows: dark glass in black frames
    for wq in plan['windows']:
        g = P(wq)
        c, u, v, L, t = axis(g)
        if L < 0.3:
            continue
        to_balcony = not outdoor.is_empty and g.distance(outdoor) < 0.12
        # the side the outside is on, and the face that is
        s_out = 1 if air.contains(Point(c[0] + v[0] * (t / 2 + 0.15), c[1] + v[1] * (t / 2 + 0.15))) else -1
        n_out = (v[0] * s_out, v[1] * s_out)
        face = facing(bounds, (c[0] + n_out[0] * t / 2, c[1] + n_out[1] * t / 2), n_out)
        sk = skin[face]
        z = zone(face, c)
        if not to_balcony and z and z[2] in ('glass', 'lilac', 'blank'):
            # under a curtain strip, behind the fluted strip (zone_dress): the window is the strip's
            continue
        wall_mat = ZONE_CLAD[z[2]] if z else CLAD[sk]
        if L >= PANORAMIC and not to_balcony and sk != 'dark':
            # a panoramic strip (the model's dark curtain glass): floor to floor in a black grid,
            # a dark panel over the slab's band
            pane(mb, c, u, v, L, t, s_out * (t / 2 - 0.08), 0.0, h, 'Window glass', frame='Frame dark', mullion=1.0)
            # (flush with the band it hides: 1 cm proud of it, no ledge)
            fc = (c[0] + v[0] * s_out * (t / 2 + 0.055), c[1] + v[1] * s_out * (t / 2 + 0.055))
            mb.box(fc[0], fc[1], -0.33, L - 0.02, 0.11, 0.48, 'Facade dark', rot=math.atan2(u[1], u[0]))
            continue
        if to_balcony:
            # (a door or window onto a loggia: wood over it, as the loggia's back wall)
            wall_mat = 'Loggia beige'
        sill = 0.0 if to_balcony else SILL
        if sill > 0:
            mb.prism(g, 0.0, sill, wall_mat, wall_mat)
        mb.prism(g, h - HEAD, h, wall_mat, wall_mat, wall_mat)
        # (on the graphite faces the long windows read as pairs of tall windows - render 4)
        mull = 0.9 if to_balcony else 2.4 if sk == 'dark' and L >= PANORAMIC else 1.4
        pane(mb, c, u, v, L, t, s_out * (t / 2 - 0.08), sill, h - HEAD, 'Window glass', mullion=mull)
    # glazing drawn in the plan (cyan): balcony rails, or glass floor to ceiling
    for gq in plan['glazing']:
        g = P(gq)
        if g.area < 0.004:
            continue
        c, u, v, L, t = axis(g)
        if L < 0.25:
            continue
        on_balcony = not outdoor.is_empty and g.distance(outdoor) < 0.15
        if on_balcony and not glass_face(*c):
            for a, b in outer_edges(g, outside) or [((c[0] - u[0] * L / 2, c[1] - u[1] * L / 2), (c[0] + u[0] * L / 2, c[1] + u[1] * L / 2))]:
                rail(a, b)
        else:
            pane(mb, c, u, v, L, t, 0.0, 0.0, h - 0.05, 'Strip glass' if glass_face(*c) else 'Tower glass', frame='Frame dark', mullion=1.0)
    # balcony parapets: glass railings (or, on Б's glazed face, glass to the ceiling)
    for pq in plan.get('parapets', []):
        g = P(pq)
        c, u, v, L, t = axis(g)
        if L < 0.25:
            continue
        a = (c[0] - u[0] * L / 2, c[1] - u[1] * L / 2)
        b = (c[0] + u[0] * L / 2, c[1] + u[1] * L / 2)
        if glass_face(*c):
            # (Б's glass corner: the curtain strips' dark mirror glass, render 4)
            pane(mb, c, u, v, L, t, 0.0, 0.0, h - 0.05, 'Strip glass', frame='Frame dark', mullion=1.0)
        else:
            for a_, b_ in outer_edges(g, outside) or [(a, b)]:
                rail(a_, b_)
    for g, face, mat in pilasters(key, plan, skin, zones):
        mb.prism_chamfer(g, -0.25, h, mat, mat if top else None, None, c=0.02)
    if zones:
        zone_dress(mb, key, plan, h, fin_on, tbar)


def pilasters(key, plan, skin, zones=True):
    """the plan's pilasters as built: (outline, face, material) - the white pilasters (grey outlines
    on the sheets) through the slab bands; in the yard faces' graphite top graphite too (render 5
    reads a dark block there; the sheets' pilasters are a metre wide and hid the dark between them
    from any angle)"""
    enc = P(plan['enclosure'])
    bounds, rim = enc.bounds, enc.exterior
    for q in plan.get('pilasters', []):
        face = None
        g = P(q)
        c = g.centroid
        e = rim.interpolate(rim.project(c))
        d = (c.x - e.x, c.y - e.y)
        k = math.hypot(*d)
        mat = 'Pilaster white'
        if k > 1e-6:
            n = (d[0] / k, d[1] / k) if not enc.contains(c) else (-d[0] / k, -d[1] / k)
            face = facing(bounds, (c.x, c.y), n)
            if skin[face] == 'dark' and SKIN[key][face] != 'dark':
                mat = 'Facade dark'
            z = zone_at(key, face, (c.x, c.y), 0.3) if zones else None
            if z and z[2] in ('glass', 'lilac'):
                # (inside a strip: the glass runs over it, its fin stands for it - photo 4103)
                continue
            if SKIN[key][face] == 'street':
                # (renders 3, 4 and the model: the pilasters stand proud of the loggias' fronts, the
                # loggias recessed between them; the sheets draw some of them behind the fronts)
                sx, sy = SIDES[face]
                gx0, gy0, gx1, gy1 = g.bounds
                if face in ('+x', '-x'):
                    line = face_line(enc, face, gy0 - 1.6, gy1 + 1.6)
                    outer = gx1 if face == '+x' else gx0
                    if line is not None and (line - outer) * sx > -0.18:
                        tip = line + sx * 0.18
                        g = g.union(box(min(outer, tip), gy0, max(outer, tip), gy1)).buffer(0)
                else:
                    line = face_line(enc, face, gx0 - 1.6, gx1 + 1.6)
                    outer = gy1 if face == '+y' else gy0
                    if line is not None and (line - outer) * sy > -0.18:
                        tip = line + sy * 0.18
                        g = g.union(box(gx0, min(outer, tip), gx1, max(outer, tip))).buffer(0)
                g = P(g.exterior.coords) if g.geom_type == 'Polygon' else max(g.geoms, key=lambda q: q.area)
        yield g, face, mat


def decor(mb, key, plan, skin, plants, base):
    """what one floor has of its own, in an object of its own (the floors that look the same share
    their meshes): the plants on its balconies where the renders show them, and on the first flat
    floor the uplights at the foot of the street faces' pilasters (render 3: a warm fan of light up
    each pilaster from the podium's roof)"""
    enc = P(plan['enclosure'])
    outside = box(*enc.buffer(30).bounds).difference(enc)
    for face, t, kind in plants:
        x0, y0, x1, y1 = REF[key]
        a = at_t(key, face, t)
        m = Point({'+x': (x1, a), '-x': (x0, a), '+y': (a, y1), '-y': (a, y0)}[face])
        sx, sy = SIDES[face]
        best = None
        for g in outdoor_rooms(plan):
            pts = list(ccw(g).exterior.coords)
            for p0, p1 in zip(pts, pts[1:]):
                L = math.dist(p0, p1)
                if L < 0.3:
                    continue
                n = ((p1[1] - p0[1]) / L, -(p1[0] - p0[0]) / L)
                mid = Point((p0[0] + p1[0]) / 2 + n[0] * 0.5, (p0[1] + p1[1]) / 2 + n[1] * 0.5)
                if n[0] * sx + n[1] * sy > 0.7 and outside.contains(mid):
                    d = LineString([p0, p1]).distance(m)
                    if best is None or d < best[0]:
                        best = (d, g, LineString([p0, p1]))
        if best is None or best[0] > 1.5:
            print(f'  ! no balcony for the plant at {key} {face} t={t}')
            continue
        _, g, edge = best
        e = edge.interpolate(edge.project(m))
        q = Point(e.x - sx * 0.45, e.y - sy * 0.45)
        rnd = random.Random(f'{key} {face} {t}')
        if kind == 'bush':
            mb.box(q.x, q.y, SLAB, 0.5, 0.5, 0.45, 'Frame dark')
            mb.blob(q.x, q.y, SLAB + 0.95, 0.46, 0.46, 0.55, 'Leaves', subdiv=2, jitter=0.09, rnd=rnd)
        else:
            mb.box(q.x, q.y, SLAB, 0.34, 0.34, 0.34, 'Frame dark')
            mb.blob(q.x, q.y, SLAB + 0.68, 0.22, 0.22, 0.36, 'Leaves light', subdiv=1, jitter=0.1, rnd=rnd)
    if not base:
        return
    for g, face, mat in pilasters(key, plan, skin):
        if face is None or SKIN[key][face] != 'street' or mat != 'Pilaster white':
            continue
        gx0, gy0, gx1, gy1 = g.bounds
        # (left to right seen from outside, so the quad faces out)
        a, b = {'+x': ((gx1 + 0.02, gy0), (gx1 + 0.02, gy1)), '-x': ((gx0 - 0.02, gy1), (gx0 - 0.02, gy0)),
                '+y': ((gx1, gy1 + 0.02), (gx0, gy1 + 0.02)), '-y': ((gx0, gy0 - 0.02), (gx1, gy0 - 0.02))}[face]
        if math.dist(a, b) < 0.2:
            continue
        mb.face([(*a, 0.0), (*b, 0.0), (*b, 4.6), (*a, 4.6)], 'Night wash', [(0, 0), (1, 0), (1, 1), (0, 1)])


def loggia_fronts(plan, enc):
    """the loggias and the strips in front of their open sides out to past the facade line (the
    rooms stop up to 0.3 m short of it, behind the parapet): where the slab's band is the loggias'
    slab edge"""
    outside = box(*enc.buffer(30).bounds).difference(enc)
    zones = []
    for g in outdoor_rooms(plan):
        zones.append(g.buffer(0.02, join_style='mitre'))
        pts = list(ccw(g).exterior.coords)
        for a, b in zip(pts, pts[1:]):
            L = math.dist(a, b)
            if L < 0.3:
                continue
            n = ((b[1] - a[1]) / L, -(b[0] - a[0]) / L)
            m = ((a[0] + b[0]) / 2 + n[0] * 0.5, (a[1] + b[1]) / 2 + n[1] * 0.5)
            if outside.contains(Point(m)):
                zones.append(Polygon([a, b, (b[0] + n[0] * 0.45, b[1] + n[1] * 0.45), (a[0] + n[0] * 0.45, a[1] + n[1] * 0.45)]))
    return unary_union(zones) if zones else Polygon()


def slab_mesh(mb, plan, h, skin, key=None, zones=True):
    enc = P(plan['enclosure'])
    mb.prism(enc.buffer(-0.04, join_style='mitre'), -0.25, SLAB, 'Stone white', 'Shop floor', 'Stone white')
    # (the loggias' floor: grey porcelain, so they read as recesses, not white shelves, from above)
    for g in outdoor_rooms(plan):
        mb.polygon_face(g.buffer(-0.01, join_style='mitre'), SLAB + 0.004, 'Loggia floor')
    ring = enc.buffer(0.1, join_style='mitre').difference(enc.buffer(-0.04, join_style='mitre'))
    # the band at the slab: white (the white grid of the renders and the model, the loggias' slab
    # edges), graphite on the graphite faces, none behind the curtain strips, Б's T and its fluted
    # strip (zone_dress: the glass runs on over the slabs there)
    loggias = loggia_fronts(plan, enc)
    bounds = enc.bounds
    cut, dark = [], []
    if zones and key in ZONES:
        x0, y0, x1, y1 = bounds
        for face, zs in ZONES[key].items():
            for t0, t1, kind, _ in zs:
                if kind not in ('glass', 'lilac', 'gold'):
                    continue
                a, b = sorted((at_t(key, face, t0), at_t(key, face, t1)))
                cut.append({'+x': box(x1 - 1.2, a, x1 + 1.0, b), '-x': box(x0 - 1.0, a, x0 + 1.2, b),
                            '+y': box(a, y1 - 1.2, b, y1 + 1.0), '-y': box(a, y0 - 1.0, b, y0 + 1.2)}[face])
    pts = list(ccw(enc).exterior.coords)
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        if L < 1e-6:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        n = (uy, -ux)
        s = skin[facing(bounds, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), n)]
        if s in ('yard', 'street'):
            continue
        # the band's stretch along this edge (a little past its ends, so no corner is left over)
        e0 = (a[0] - ux * 0.12, a[1] - uy * 0.12)
        e1 = (b[0] + ux * 0.12, b[1] + uy * 0.12)
        q = Polygon([(e0[0] - n[0] * 0.1, e0[1] - n[1] * 0.1), (e1[0] - n[0] * 0.1, e1[1] - n[1] * 0.1),
                     (e1[0] + n[0] * 0.2, e1[1] + n[1] * 0.2), (e0[0] + n[0] * 0.2, e0[1] + n[1] * 0.2)])
        (cut if s == 'street' else dark).append(q)
    keep = ring.difference(unary_union(cut).difference(loggias)) if cut else ring
    # (the loggias' slab edges on the graphite faces graphite as well - render 4)
    dark_g = unary_union(dark) if dark else Polygon()
    mb.prism_chamfer(keep.difference(dark_g), -0.32, 0.14, 'White band', 'White band', 'White band', c=0.02)
    if not dark_g.is_empty:
        mb.prism_chamfer(keep.intersection(dark_g), -0.32, 0.14, 'Facade dark', 'Facade dark', 'Facade dark', c=0.02)


def crown(mb, block, plan, zr):
    """the roof: on А and В a terrace with a tall white parapet frame, posts, a railing; on Б a low
    glass parapet between white bands (renders 1, 2, 4: Б has no frame - the model's frame stood
    3.5-4 m over Б's roof, the fitted cameras of renders 1 and 2 put Б's top 24-26 px lower); plant
    rooms over the stairs and lifts; solar panels"""
    enc = P(plan['enclosure'])
    # (the top floors' corner terraces are open to the sky, the parapet and the crown's frame step
    # round them: Б's on render 4, А's and В's on render 5)
    terr = [P(r['poly']) for a in plan['apartments'] for r in a['rooms'] + a['balconies'] if r['kind'] == 'terrace']
    if terr:
        # (the parapet's 10 cm strip outside the terrace goes with it)
        rest = enc.difference(unary_union(terr).buffer(0.02, join_style='mitre'))
        rest = rest.buffer(-0.2, join_style='mitre').buffer(0.2, join_style='mitre')
        enc = max(parts(rest), key=lambda q: q.area)
    roof = enc.buffer(-0.05, join_style='mitre')
    mb.prism(roof, zr - 0.25, zr + 0.15, 'Stone white', 'Roof', None)
    if block['key'] == 'B':
        ring = enc.buffer(0.18, join_style='mitre').difference(enc.buffer(-0.3, join_style='mitre'))
        mb.prism_chamfer(ring, zr - 0.3, zr + 0.35, 'Stone white', 'White band', None, c=0.02)
        pts = list(enc.buffer(-0.06, join_style='mitre').exterior.coords)
        mb.ribbon(pts, zr + 0.35, zr + 1.3, 'Railing glass', closed=True, double=True)
        band = enc.buffer(0.12, join_style='mitre').difference(enc.buffer(-0.18, join_style='mitre'))
        mb.prism_chamfer(band, zr + 1.3, zr + 1.55, 'White band', 'White band', 'White band', c=0.02)
        # (the light lines of render 2: both edges of the cornice and of the parapet's top band)
        for zz, off in ((zr - 0.3, 0.18), (zr + 0.26, 0.18), (zr + 1.3, 0.12), (zr + 1.46, 0.12)):
            line_ring = enc.buffer(off + 0.03, join_style='mitre').difference(enc.buffer(off - 0.05, join_style='mitre'))
            mb.prism(line_ring, zz, zz + 0.09, 'Night line', 'Night line', 'Night line')
    else:
        ring = enc.buffer(0.18, join_style='mitre').difference(enc.buffer(-0.3, join_style='mitre'))
        mb.prism_chamfer(ring, zr - 0.3, zr + 1.15, 'Stone white', 'White band', None, c=0.02)
        # the crown band, standing proud
        band = enc.buffer(0.55, join_style='mitre').difference(enc.buffer(0.05, join_style='mitre'))
        mb.prism_chamfer(band, zr + 0.6, zr + 1.35, 'White band', 'White band', 'White band', c=0.03)
        # (a thin warm wood line along the middle of the band and of the frame's top rail - render 4
        # by day; at night the light lines run along their edges, renders 2, 3)
        for off, za in ((0.55, zr + 0.94), (0.45, zr + 5.12)):
            stripe = enc.buffer(off + 0.012, join_style='mitre').difference(enc.buffer(off - 0.02, join_style='mitre'))
            mb.prism(stripe, za, za + 0.07, 'Strip wood', None, None)
        # the frame's posts and top rail (renders: a white frame over the terrace edge, its top about
        # 1.6 storeys over the roof - render 2, 52 px against 32 px a storey at В's corner)
        line = enc.buffer(0.3, join_style='mitre').exterior
        L = line.length
        n = max(8, int(L / 6.5))
        for k in range(n):
            p = line.interpolate(k * L / n)
            mb.box(p.x, p.y, zr + 1.35, 0.35, 0.35, 3.6, 'Stone white')
        top_ring = enc.buffer(0.45, join_style='mitre').difference(enc.buffer(0.12, join_style='mitre'))
        mb.prism_chamfer(top_ring, zr + 4.95, zr + 5.35, 'White band', 'White band', 'White band', c=0.03)
        # the light lines of the night renders (renders 2, 3): warm and broad, along both edges of
        # the crown band and of the frame's top rail - the rail's underside glows
        for zz, off in ((zr + 0.6, 0.55), (zr + 1.27, 0.55), (zr + 4.95, 0.45), (zr + 5.27, 0.45)):
            line_ring = enc.buffer(off + 0.03, join_style='mitre').difference(enc.buffer(off - 0.05, join_style='mitre'))
            mb.prism(line_ring, zz, zz + 0.09, 'Night line', 'Night line', 'Night line')
        # railing on the parapet: a dark metal balustrade, bars 0.3 m apart (renders 4, 5: one sees
        # through it; a solid dark ribbon here read as a black band round the roof)
        ring_line = enc.buffer(-0.12, join_style='mitre').exterior
        pts = list(ring_line.coords)
        for zz in (zr + 1.15, zr + 2.15):
            mb.tube(pts, [zz] * len(pts), [zz + 0.05] * len(pts), 0.05, 'Frame dark', closed=True)
        for k in range(int(ring_line.length / 0.3)):
            q = ring_line.interpolate(k * 0.3)
            mb.box(q.x, q.y, zr + 1.2, 0.03, 0.03, 0.95, 'Frame dark')
        # slim cypresses in planters behind the balustrade, about every 3.5 m (renders 1-5)
        rnd = random.Random(f"crown {block['key']}")
        pots = enc.buffer(-0.75, join_style='mitre').exterior
        for k in range(int(pots.length / 3.5)):
            q = pots.interpolate((k + 0.5) * pots.length / int(pots.length / 3.5))
            potted_cypress(mb, q.x, q.y, zr + 0.15, rnd.uniform(1.5, 1.9), rnd)
    # plant rooms over the stairs and lift halls
    core = unary_union([P(c) for c in plan['common']]).buffer(0.3, join_style='mitre')
    for lf in plan.get('lifts', []):
        core = core.union(P(lf['shaft']).buffer(0.3, join_style='mitre'))
    core = core.intersection(roof.buffer(-1.5))
    for q in parts(core.buffer(0.6).buffer(-0.6)):
        if q.area < 6:
            continue
        q = q.simplify(0.3)
        mb.prism_chamfer(q, zr + 0.15, zr + 3.6, 'Plant room', None, None, c=0.02)
        mb.prism(q.buffer(0.25, join_style='mitre'), zr + 3.6, zr + 3.9, 'White band', 'Roof', 'White band')
        # (render 4: graphite tiles, a frosted glass parapet on top, a glazed door to the terrace)
        mb.ribbon(list(q.buffer(0.12, join_style='mitre').exterior.coords), zr + 3.9, zr + 4.75, 'Railing glass', closed=True, double=True)
        cs = list(ccw(q).exterior.coords)
        a, b = max(zip(cs, cs[1:]), key=lambda e: math.dist(*e))
        L = math.dist(a, b)
        if L > 2.5:
            u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
            n = (u[1], -u[0])
            m = ((a[0] + b[0]) / 2 + n[0] * 0.03, (a[1] + b[1]) / 2 + n[1] * 0.03)
            pane(mb, m, u, n, 1.8, 0.0, 0.0, zr + 0.15, zr + 2.55, 'Window glass', mullion=0.9)
    # solar panels on the free roof (the renders' roofs: plant rooms and panels, no trees - the
    # small trees along the edge read as trees standing in the sky)
    free = roof.buffer(-2.2).difference(core.buffer(1.2))
    solar_arrays(mb, free, zr + 0.15, SOLAR[block['key']])


def frame(b):
    a = math.radians(b['rot'])
    cx, cy = b['centre']
    ca, sa = math.cos(a), math.sin(a)
    return a, (lambda x, y: (cx + ca * x - sa * y, cy + sa * x + ca * y))


def footprint(key, plans):
    b = BLOCKS[key]
    _, to_site = frame(b)
    return Polygon([to_site(x, y) for x, y in plans[b['plans'][FIRST_FLAT_FLOOR]]['enclosure']]).buffer(0)


def build_block(key, mats, root_col, plans):
    b = BLOCKS[key]
    b['key'] = key
    col = get_collection(f'Block {key}', root_col)
    a, to_site = frame(b)
    cx, cy = b['centre']

    def put(ob, z=0.0):
        ob.location = (cx, cy, z)
        ob.rotation_euler = (0, 0, a)
        return ob

    cache, floors = {}, []
    pick_col = get_collection(f'Picking {key}', col)
    top_floor = b['floors']
    REF[key] = P(plans[TYP[key]]['enclosure']).bounds
    for f in range(FIRST_FLAT_FLOOR, top_floor + 1):
        pk = b['plans'][f]
        z, h = level(f), height(f)
        skin = skin_of(key, f, top_floor)
        # (В's floors 20-22 stand clear of Б's roof: their face to Б has the four windows of the
        # 23rd floor's sheet, as renders 1, 4 and the model show on every floor over Б; the typical
        # sheet draws that wall blind, for the floors next to Б - 30.10.2026)
        fpk = 'V_23' if key == 'V' and 20 <= f <= 22 else pk
        # (Б's top floor is set back, its own facade - the photos: no T, no strips there)
        zones = not (key == 'B' and f == top_floor)
        fin_on = f <= top_floor - FIN_STOP
        tbar = key == 'B' and f == top_floor - 1
        ck = (fpk, f == top_floor, tuple(sorted(skin.items())), zones, fin_on, tbar)
        if ck not in cache:
            sm, wm = MeshBuilder(), MeshBuilder()
            slab_mesh(sm, plans[fpk], h, skin, key, zones)
            facade_floor(wm, b, plans[fpk], h, skin, top=f == top_floor, zones=zones, fin_on=fin_on, tbar=tbar)
            nm = f'{key} {fpk} {len(cache)}'
            cache[ck] = (sm.to_mesh(nm + ' slab', mats), wm.to_mesh(nm + ' walls', mats))
        sm, wm = cache[ck]
        for part, me in (('slab', sm), ('walls', wm)):
            ob = put(make_object(f"{key} {'floor' if part == 'slab' else 'walls'} {f:02d}", me, col), z)
            ob['tower'], ob['floor'], ob['part'] = key, f, part
        if (key, f) in PLANTS or f == FIRST_FLAT_FLOOR:
            dm = MeshBuilder()
            decor(dm, key, plans[fpk], skin, PLANTS.get((key, f), []), f == FIRST_FLAT_FLOOR)
            if dm.faces:
                nm = f'{key} decor {f:02d}'
                ob = put(make_object(nm, dm.to_mesh(nm, mats), col), z)
                ob['tower'], ob['floor'], ob['part'] = key, f, 'decor'
        for i, apt in enumerate(plans[pk]['apartments']):
            mb = MeshBuilder()
            mb.prism(P(apt['outline']).buffer(0.2, join_style='mitre').simplify(0.1), -0.15, h - 0.1, 'Pick', 'Pick', 'Pick')
            nm = f'pick {key} {f:02d} {i}'
            ob = put(make_object(nm, mb.to_mesh(nm, {'Pick': pick_material()}), pick_col), z + SLAB)
            ob['tower'], ob['floor'], ob['unit'], ob['pick'] = key, f, i, 1
            ob.hide_render = True
        floors.append(dict(floor=f, z=round(z, 3), h=round(h, 3), plan=pk))
    top = plans[b['plans'][top_floor]]
    zr = level(top_floor + 1)
    mb = MeshBuilder()
    crown(mb, b, top, zr)
    if key in ('A', 'V'):
        # the top floor's corner terraces: a pair of cypresses in planters by the walls (render 5)
        rnd = random.Random(f'{key} terraces')
        zt = level(top_floor) + SLAB
        for apt in top['apartments']:
            for r in apt['rooms'] + apt['balconies']:
                if r['kind'] != 'terrace':
                    continue
                g = P(r['poly'])
                inner = g.buffer(-0.5, join_style='mitre')
                if inner.is_empty:
                    continue
                # (the corner of the terrace furthest from the open air: by the flat's walls)
                far = max(inner.exterior.coords, key=lambda c: P(top['enclosure']).exterior.distance(Point(c)))
                c0 = g.centroid
                for k in (0.0, 0.45):
                    qx, qy = far[0] + (c0.x - far[0]) * k, far[1] + (c0.y - far[1]) * k
                    potted_cypress(mb, qx, qy, zt, rnd.uniform(1.6, 2.0), rnd)
    if key == 'B':
        # the top floor's corner terrace, open to the sky: three small trees in white pots along its
        # inner sides, a round table and two chairs (render 4)
        rnd = random.Random('B terrace')
        for apt in top['apartments']:
            for r in apt['rooms'] + apt['balconies']:
                if r['kind'] != 'terrace':
                    continue
                g = P(r['poly'])
                x0, y0, x1, y1 = g.bounds
                zt = level(top_floor) + SLAB
                for tx, ty in ((x0 + 0.8, y1 - 1.2), (x0 + 0.8, y0 + 0.8), (x1 - 1.2, y0 + 0.8)):
                    if g.buffer(-0.35).contains(Point(tx, ty)):
                        potted_tree(mb, tx, ty, zt, rnd)
                # (qx, qy: cx, cy are the block's centre, put() places the roof by them)
                qx, qy = x0 + (x1 - x0) * 0.58, y0 + (y1 - y0) * 0.58
                mb.prism(Point(qx, qy).buffer(0.45, quad_segs=4), zt + 0.7, zt + 0.74, 'Stone white', 'Stone white', 'Stone white')
                mb.box(qx, qy, zt, 0.08, 0.08, 0.7, 'Frame dark')
                for dx, dy in ((0.75, 0.0), (0.0, 0.75)):
                    mb.box(qx + dx, qy + dy, zt + 0.42, 0.45, 0.45, 0.05, 'Frame dark')
                    mb.box(qx + dx * 1.25, qy + dy * 1.25, zt + 0.42, 0.45 if dy else 0.05, 0.05 if dy else 0.45, 0.45, 'Frame dark')
    ob = put(make_object(f'{key} roof', mb.to_mesh(f'{key} roof', mats), col))
    ob['tower'], ob['part'] = key, 'roof'
    return dict(key=key, label=b['label'], tj=b['tj'], centre=[round(v, 3) for v in b['centre']], rot=round(b['rot'], 3),
                plan_centre=[0.0, 0.0], slab=SLAB, floors=floors, levels=top_floor, top=round(zr, 3), sales=True,
                outline=[[round(x, 2), round(y, 2)] for x, y in footprint(key, plans).exterior.coords])


def joints(mats, col, plans):
    """the expansion joints between the blocks - the sheets draw Б about a metre off В and off А -
    closed from the podium's top to Б's roof by a graphite filler, so the blocks read joined, as the
    renders and the model have them (one saw through the joints to the yard - 30.10.2026). Only the
    narrow joint: the wider notches where the faces step stay open"""
    fp = {k: footprint(k, plans) for k in BLOCKS}
    mb = MeshBuilder()
    for k1, k2 in (('B', 'V'), ('A', 'B')):
        narrow = fp[k1].buffer(0.8, join_style='mitre').intersection(fp[k2].buffer(0.8, join_style='mitre'))
        g = narrow.buffer(0.25, join_style='mitre').difference(fp[k1]).difference(fp[k2])
        top = level(min(BLOCKS[k1]['floors'], BLOCKS[k2]['floors']) + 1) + 1.55
        for q in parts(g):
            if q.area > 0.5:
                mb.prism(q, level(FIRST_FLAT_FLOOR) - 0.3, top, 'Facade dark', 'Roof', None)
    return make_object('Joints', mb.to_mesh('Joints', mats), get_collection('Joints', col))
