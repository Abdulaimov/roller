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

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from complex.geom import MeshBuilder, ccw, get_collection, log_tree, make_object
from complex.towers import add_rails, pick_material

from .config import BLOCKS, FIRST_FLAT_FLOOR, SLAB, height, level

# The finish of each face of a block, on the sheets' axes: +x faces кӯчаи Ҳусейнзода, +y кӯчаи
# Нарзиқулова (28.10.2026, the user on renders 1-4: «the house is all white, there it is grey,
# mirror-like; on block В you can hardly see a window»):
#   street - silver cladding, the windows glass floor to floor, no white band across;
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
INNER = 'Facade white'   # the walls' sides indoors (seen only in the cut-away views)
SIDES = {'+x': (1.0, 0.0), '-x': (-1.0, 0.0), '+y': (0.0, 1.0), '-y': (0.0, -1.0)}
SILL, HEAD = 0.45, 0.35
# the balconies' glass rail stands on a low curb over the slab's edge (renders 1, 4, 6: a thin white
# edge, tinted glass above it - not the 0.4 m white upstand of the shared rail)
LOGGIA_CURB = 0.1
PANORAMIC = 2.4   # m: windows this long on the sheets are the model's dark curtain-glass strips
GLASS_FACE = {'B': lambda x, y: x > 12.5}   # Б: the balconies on the east face are glazed full height
SOLAR = {'A': 4, 'B': 2, 'V': 9}   # PV arrays on the roof (two rows of panels each), counted on renders 4 and 5


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


def facade_floor(mb, block, plan, h, skin, top=False):
    key = block['key']
    enc = P(plan['enclosure'])
    bounds = enc.bounds
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

    def finish(m, n):
        """what a wall's side at m looking along n is clad in"""
        p = Point(m[0] + n[0] * 0.15, m[1] + n[1] * 0.15)
        if outside.contains(p):
            return CLAD[skin[facing(bounds, m, n)]]
        if recess.contains(p):
            return CLAD['dark']
        if not outdoor.is_empty and (outdoor.contains(p) or outdoor.distance(Point(m)) < 0.4):
            # the back walls of the loggias and their jambs: warm wood (renders 1, 2, 4, 6)
            return 'Loggia beige'
        q = Point(m)
        if rim.distance(q) < 0.6:
            # a window's jamb, the reveal: the face's own finish
            e = rim.interpolate(rim.project(q))
            d = (e.x - m[0], e.y - m[1])
            k = math.hypot(*d) or 1.0
            return CLAD[skin[facing(bounds, m, (d[0] / k, d[1] / k))]]
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
    # the loggias' downlights: two round lamps in each loggia's ceiling, lit at night (renders 1-3:
    # the warm light in the loggias is theirs, the wood itself stays a dark brown)
    for g in out_rooms:
        c, u, v, L, t = axis(g)
        k = 2 if L > 2.4 else 1
        for i in range(k):
            s = ((i + 0.5) / k - 0.5) * L * 0.6
            mb.box(c[0] + u[0] * s, c[1] + u[1] * s, h - 0.27, 0.16, 0.16, 0.02, 'Night line', rot=math.atan2(u[1], u[0]))
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
        sk = skin[facing(bounds, (c[0] + n_out[0] * t / 2, c[1] + n_out[1] * t / 2), n_out)]
        if not to_balcony and sk == 'street':
            # the street faces (renders 1-4): glass floor to floor in a dark grid - mullions under a
            # metre apart, a transom at the rail's height - just in front of the slab's edge, so
            # the strips run on from floor to floor and the windows are lost in the glass
            pane(mb, c, u, v, L, t, s_out * (t / 2 - 0.03), 0.0, h, 'Window glass', frame='Frame dark',
                 mullion=0.9, transom=1.1)
            continue
        wall_mat = CLAD[sk]
        if L >= PANORAMIC and not to_balcony:
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
        pane(mb, c, u, v, L, t, s_out * (t / 2 - 0.08), sill, h - HEAD, 'Window glass', mullion=1.4 if not to_balcony else 0.9)
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
                add_rails(mb, [[a, b]], 0.0, post_step=0, fascia=LOGGIA_CURB)
        else:
            pane(mb, c, u, v, L, t, 0.0, 0.0, h - 0.05, 'Tower glass', frame='Frame dark', mullion=1.0)
    # balcony parapets: glass railings (or, on Б's glazed face, glass to the ceiling)
    for pq in plan.get('parapets', []):
        g = P(pq)
        c, u, v, L, t = axis(g)
        if L < 0.25:
            continue
        a = (c[0] - u[0] * L / 2, c[1] - u[1] * L / 2)
        b = (c[0] + u[0] * L / 2, c[1] + u[1] * L / 2)
        if glass_face(*c):
            pane(mb, c, u, v, L, t, 0.0, 0.0, h - 0.05, 'Tower glass', frame='Frame dark', mullion=1.0)
        else:
            for a_, b_ in outer_edges(g, outside) or [(a, b)]:
                add_rails(mb, [[a_, b_]], 0.0, post_step=0, fascia=LOGGIA_CURB)
    # the white pilasters (grey outlines on the sheets), through the slab bands; in the yard faces'
    # graphite top graphite too (render 5 reads a dark block there; the sheets' pilasters are a
    # metre wide and hid the dark between them from any angle)
    for q in plan.get('pilasters', []):
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
        mb.prism_chamfer(g, -0.25, h, mat, mat if top else None, None, c=0.02)


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


def slab_mesh(mb, plan, h, skin):
    enc = P(plan['enclosure'])
    mb.prism(enc.buffer(-0.04, join_style='mitre'), -0.25, SLAB, 'Stone white', 'Shop floor', 'Stone white')
    # (the loggias' floor: grey porcelain, so they read as recesses, not white shelves, from above)
    for g in outdoor_rooms(plan):
        mb.polygon_face(g.buffer(-0.01, join_style='mitre'), SLAB + 0.004, 'Loggia floor')
    ring = enc.buffer(0.1, join_style='mitre').difference(enc.buffer(-0.04, join_style='mitre'))
    # the band at the slab: white round the loggias (their slab edges) and on the yard faces,
    # graphite on the graphite faces, none across the street faces (renders 1-4: the glass and the
    # cladding run on over the slabs there)
    loggias = loggia_fronts(plan, enc)
    bounds = enc.bounds
    cut, dark = [], []
    pts = list(ccw(enc).exterior.coords)
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        if L < 1e-6:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        n = (uy, -ux)
        s = skin[facing(bounds, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), n)]
        if s == 'yard':
            continue
        # the band's stretch along this edge (a little past its ends, so no corner is left over)
        e0 = (a[0] - ux * 0.12, a[1] - uy * 0.12)
        e1 = (b[0] + ux * 0.12, b[1] + uy * 0.12)
        q = Polygon([(e0[0] - n[0] * 0.1, e0[1] - n[1] * 0.1), (e1[0] - n[0] * 0.1, e1[1] - n[1] * 0.1),
                     (e1[0] + n[0] * 0.2, e1[1] + n[1] * 0.2), (e0[0] + n[0] * 0.2, e0[1] + n[1] * 0.2)])
        (cut if s == 'street' else dark).append(q)
    keep = ring.difference(unary_union(cut).difference(loggias)) if cut else ring
    dark_g = unary_union(dark).difference(loggias) if dark else Polygon()
    mb.prism_chamfer(keep.difference(dark_g), -0.32, 0.14, 'White band', 'White band', 'White band', c=0.02)
    if not dark_g.is_empty:
        mb.prism_chamfer(keep.intersection(dark_g), -0.32, 0.14, 'Facade dark', 'Facade dark', 'Facade dark', c=0.02)


def crown(mb, block, plan, zr):
    """the roof: on А and В a terrace with a tall white parapet frame, posts, a railing; on Б a low
    glass parapet between white bands (renders 1, 2, 4: Б has no frame - the model's frame stood
    3.5-4 m over Б's roof, the fitted cameras of renders 1 and 2 put Б's top 24-26 px lower); plant
    rooms over the stairs and lifts; solar panels"""
    enc = P(plan['enclosure'])
    roof = enc.buffer(-0.05, join_style='mitre')
    mb.prism(roof, zr - 0.25, zr + 0.15, 'Stone white', 'Roof', None)
    if block['key'] == 'B':
        ring = enc.buffer(0.18, join_style='mitre').difference(enc.buffer(-0.3, join_style='mitre'))
        mb.prism_chamfer(ring, zr - 0.3, zr + 0.35, 'Stone white', 'White band', None, c=0.02)
        pts = list(enc.buffer(-0.06, join_style='mitre').exterior.coords)
        mb.ribbon(pts, zr + 0.35, zr + 1.3, 'Railing glass', closed=True, double=True)
        band = enc.buffer(0.12, join_style='mitre').difference(enc.buffer(-0.18, join_style='mitre'))
        mb.prism_chamfer(band, zr + 1.3, zr + 1.55, 'White band', 'White band', 'White band', c=0.02)
        line_ring = enc.buffer(0.14, join_style='mitre').difference(enc.buffer(0.08, join_style='mitre'))
        mb.prism(line_ring, zr + 1.27, zr + 1.31, 'Night line', 'Night line', 'Night line')
    else:
        ring = enc.buffer(0.18, join_style='mitre').difference(enc.buffer(-0.3, join_style='mitre'))
        mb.prism_chamfer(ring, zr - 0.3, zr + 1.15, 'Stone white', 'White band', None, c=0.02)
        # the crown band, standing proud
        band = enc.buffer(0.55, join_style='mitre').difference(enc.buffer(0.05, join_style='mitre'))
        mb.prism_chamfer(band, zr + 0.6, zr + 1.35, 'White band', 'White band', 'White band', c=0.03)
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
        # the light lines of the night renders: round the crown band and the frame's top rail
        for zz in (zr + 1.36, zr + 4.92):
            line_ring = enc.buffer(0.57 if zz < zr + 2 else 0.47, join_style='mitre').difference(enc.buffer(0.5 if zz < zr + 2 else 0.4, join_style='mitre'))
            mb.prism(line_ring, zz, zz + 0.05, 'Night line', 'Night line', 'Night line')
        # railing on the parapet
        pts = list(enc.buffer(-0.12, join_style='mitre').exterior.coords)
        mb.tube(pts, [zr + 1.15] * len(pts), [zr + 2.2] * len(pts), 0.04, 'Frame dark', closed=True)
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
    for f in range(FIRST_FLAT_FLOOR, top_floor + 1):
        pk = b['plans'][f]
        z, h = level(f), height(f)
        skin = skin_of(key, f, top_floor)
        ck = (pk, f == top_floor, tuple(sorted(skin.items())))
        if ck not in cache:
            sm, wm = MeshBuilder(), MeshBuilder()
            slab_mesh(sm, plans[pk], h, skin)
            facade_floor(wm, b, plans[pk], h, skin, top=f == top_floor)
            nm = f'{key} {pk} {len(cache)}'
            cache[ck] = (sm.to_mesh(nm + ' slab', mats), wm.to_mesh(nm + ' walls', mats))
        sm, wm = cache[ck]
        for part, me in (('slab', sm), ('walls', wm)):
            ob = put(make_object(f"{key} {'floor' if part == 'slab' else 'walls'} {f:02d}", me, col), z)
            ob['tower'], ob['floor'], ob['part'] = key, f, part
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
    ob = put(make_object(f'{key} roof', mb.to_mesh(f'{key} roof', mats), col))
    ob['tower'], ob['part'] = key, 'roof'
    return dict(key=key, label=b['label'], tj=b['tj'], centre=[round(v, 3) for v in b['centre']], rot=round(b['rot'], 3),
                plan_centre=[0.0, 0.0], slab=SLAB, floors=floors, levels=top_floor, top=round(zr, 3), sales=True,
                outline=[[round(x, 2), round(y, 2)] for x, y in footprint(key, plans).exterior.coords])
