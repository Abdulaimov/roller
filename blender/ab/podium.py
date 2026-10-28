"""Floors 1-2 of every block: shops, and the two-storey podium round blocks A, Б and В (genplan "2-ош.").

The shop front follows the outline in bays of about 3.3 m: white stone portals two storeys high on
dark grey piers, clear glass on both floors with a dark signage band between them (renders 1 and 3).
Behind the glass the shops are fitted out so they read from the street: stone floor, ceiling with
light strips, partitions every 10-14 m, shelving, racks and counters, and people (the viewer draws
them from PEOPLE). Residential entrances on the courtyard side of the slab blocks get a canopy.
"""
import math
import random
import zlib

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from complex.geom import MeshBuilder, make_object, resample, ring_coords

from . import config

PEOPLE = []     # [x, y, z, kind] site metres, filled by build_base
TREES = []      # trees on the podium roof: [x, y, z, h, r, kind]
# the shop portals on the street faces, where a sign can go on the dark frieze over the glass (the
# viewer's sign layer, src/signs.js): [block, face, bay, x0, y0, x1, y1, z0, z1, nx, ny] site metres,
# the bay's ends on the facade plane, the frieze's band, the way the face looks
SHOPS = []
_block = None   # the block being built (build_base), for site coordinates
# floor heights of the block being built (build_base sets them: the tower's podium is taller)
GROUND, SECOND = config.GROUND, config.SECOND
TOP = GROUND + SECOND   # roof of the podium / level of floor 3
BAY = 3.3


def to_plan(b, pts):
    a = math.radians(b['rot'])
    ca, sa = math.cos(a), math.sin(a)
    cx, cy = b['centre']
    return [(ca * (x - cx) + sa * (y - cy), -sa * (x - cx) + ca * (y - cy)) for x, y in pts]


def to_site(b, x, y):
    a = math.radians(b['rot'])
    ca, sa = math.cos(a), math.sin(a)
    cx, cy = b['centre']
    return cx + ca * x - sa * y, cy + sa * x + ca * y


def poster(mb, a, b, z0, z1, nx, ny, off=0.06):
    """A lit poster panel (light box) between plan points a and b, facing out (n), UVs 0..1."""
    p0 = (a[0] + nx * off, a[1] + ny * off)
    p1 = (b[0] + nx * off, b[1] + ny * off)
    # p0 -> p1 runs left to right seen from outside; v is flipped for the canvas texture (flipY) of the viewer
    mb.face([(*p0, z0), (*p1, z0), (*p1, z1), (*p0, z1)], 'Poster', [(0, 1), (1, 1), (1, 0), (0, 0)])
    # white frame round it
    for q0, q1, za, zb in ((p0, p1, z0 - 0.12, z0), (p0, p1, z1, z1 + 0.12)):
        mb.face([(*q0, za), (*q1, za), (*q1, zb), (*q0, zb)], 'Stone white')


# the posters (lit boxes standing out of the shop front and up past the podium roof): plan x on the
# street face per block (render 1: Б one in the middle, В two; render 2: Г, Д one each)
POSTERS = {'B': [-2.5], 'V': [23.5, -8.5], 'G': [-2.5], 'D': [-2.5]}
PORTAL = 3.3     # a shop portal: 2.6 m of glass between two white jambs of 0.35 m
PIER = 1.2       # dark stone pier between the portals (bay pitch 4.5 m, renders 1 and 3)


def night_wash(mb, a, b, z0, z1):
    """a warm uplight's beam on a stone face from plan point a to b (UVs: v 0 at the fixture)"""
    if z1 - z0 > 0.3:
        mb.face([(*a, z0), (*b, z0), (*b, z1), (*a, z1)], 'Night wash', [(0, 0), (1, 0), (1, 1), (0, 1)])


def shop_front(mb, outline, rnd, key=None):
    """Brick blocks (renders 1 and 3): dark graphite stone piers; in each bay a window two storeys
    high in a white stone portal stepped in near its top (the jambs' outer half stops 1.5 m short),
    a thin dark transom at the second floor; a dark stone frieze over the portals with a white
    line; a few posters (lit boxes) on the street face standing out and up past the podium roof."""
    pts = ring_coords(outline)
    glass_top = TOP - 2.1
    posters = POSTERS.get(key, [])
    faces = -1
    for a, b in zip(pts, pts[1:] + pts[:1]):
        L = math.dist(a, b)
        if L < 0.3:
            continue
        faces += 1
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        nx, ny = uy, -ux
        rot = math.atan2(uy, ux)
        P = lambda s, off=0.0: (a[0] + ux * s + nx * off, a[1] + uy * s + ny * off)

        def bx(s0, s1, o0, o1, z0, z1, mat, top=True):
            if s1 - s0 < 0.01:
                return
            c = P((s0 + s1) / 2, (o0 + o1) / 2)
            mb.box(c[0], c[1], z0, s1 - s0, o1 - o0, z1 - z0, mat, rot=rot, top=top)
        street = ny > 0.5 and L > 6      # the faces towards the street (+y)
        pitch = PORTAL + PIER
        # portals only where they fit with a pier's width of dark stone at both ends of the face
        # (short faces at the bends of the outline stay dark stone)
        nb = int((L - PIER) // pitch) if L >= PORTAL + 2 * PIER else 0
        margin = (L - (nb * pitch - PIER)) / 2
        # the dark stone face over the whole length: piers, frieze, the ends
        mb.quad_wall(a, b, glass_top, TOP, 'Stone dark')
        at = 0.0
        for k in range(nb):
            s0 = margin + k * pitch
            s1 = s0 + PORTAL
            mb.quad_wall(P(at), P(s0), 0.0, glass_top, 'Stone dark')
            at = s1
            # a poster in this bay?
            sm = (s0 + s1) / 2
            px = a[0] + ux * sm   # plan x of the bay (the street face runs along x)
            if street and any(abs(px - q) < pitch / 2 for q in posters):
                mb.quad_wall(P(s0), P(s1), 0.0, glass_top, 'Stone dark')
                bx(s0 - 0.15, s1 + 0.15, 0.0, 0.45, 2.4, TOP + 1.6, 'Shop frame')
                poster(mb, P(s0 + 0.1, 0.48), P(s1 - 0.1, 0.48), 2.7, TOP + 1.3, 0, 0, off=0.0)
                continue
            if street:
                q0, q1, qn = to_site(_block, *P(s0)), to_site(_block, *P(s1)), to_site(_block, *P(sm, 1.0))
                qm = to_site(_block, *P(sm))
                SHOPS.append([key, faces, k, round(q0[0], 3), round(q0[1], 3), round(q1[0], 3), round(q1[1], 3),
                              round(glass_top + 0.3, 3), round(TOP - 1.0, 3), round(qn[0] - qm[0], 4), round(qn[1] - qm[1], 4)])
            # white portal: jambs (outer half stops 1.5 m short of the top: the step), head
            fr = 0.35
            for js in (s0, s1 - fr):
                bx(js, js + fr, -0.02, 0.22, 0.0, glass_top + 0.3, 'Stone white')
                bx(js + (0 if js == s0 else fr / 2), js + (fr / 2 if js == s0 else fr), 0.22, 0.42, 0.0, glass_top - 1.5, 'Stone white')
                # at night a warm uplight on each jamb (the night renders)
                ho = (js, js + fr / 2) if js == s0 else (js + fr / 2, js + fr)
                ii = (js + fr / 2, js + fr) if js == s0 else (js, js + fr / 2)
                night_wash(mb, P(ho[0], 0.432), P(ho[1], 0.432), 0.05, glass_top - 1.5)
                night_wash(mb, P(ii[0], 0.232), P(ii[1], 0.232), 0.05, glass_top + 0.3)
                night_wash(mb, P(ho[0], 0.232), P(ho[1], 0.232), glass_top - 1.5, glass_top + 0.3)
            bx(s0, s1, -0.02, 0.22, glass_top, glass_top + 0.3, 'Stone white')
            # the window: glass set back, a dark transom at the second floor, two mullions, doors
            g0, g1 = s0 + fr, s1 - fr
            gw = g1 - g0
            mb.quad_wall(P(g0, -0.12), P(g1, -0.12), 0.0, glass_top, 'Shop glass')
            for z0, z1 in ((0.0, 0.1), (GROUND - 0.2, GROUND + 0.1), (glass_top - 0.12, glass_top)):
                bx(g0, g1, -0.14, -0.04, z0, z1, 'Shop frame')
            for e in (g0 + 0.03, g0 + gw / 3, g0 + 2 * gw / 3, g1 - 0.03):
                bx(e - 0.03, e + 0.03, -0.14, -0.04, 0.0, glass_top, 'Shop frame')
            # reveals
            for e, sg in ((g0, 1), (g1, -1)):
                mb.quad_wall(P(e), P(e, -0.12), 0.0, glass_top, 'Stone white') if sg > 0 else mb.quad_wall(P(e, -0.12), P(e), 0.0, glass_top, 'Stone white')
        mb.quad_wall(P(at), P(L), 0.0, glass_top, 'Stone dark')
        # the frieze: a slim white line, a dark stone cornice at the podium roof
        bx(0.0, L, -0.02, 0.12, TOP - 1.0, TOP - 0.92, 'Stone white')
        bx(0.0, L, -0.05, 0.3, TOP - 0.25, TOP + 0.05, 'Stone dark')
        # LED lines at night along both (the night renders)
        mb.quad_wall(P(0.0, 0.127), P(L, 0.127), TOP - 0.99, TOP - 0.93, 'Night line')
        mb.quad_wall(P(0.0, 0.307), P(L, 0.307), TOP - 0.05, TOP + 0.03, 'Night line')


def glass_front(mb, outline, rnd):
    """Block A's podium (render 3): two storeys of shop glazing in bays, thin dark mullions and a
    transom; between the bays dark grey stone piers and, every few bays, a wider pale grey stone
    panel; a thick white band at the second floor and a thicker one at the roof, both rounded at
    the corners and standing out over the pavement; a dark strip under each band; a glass
    balustrade on the roof terrace."""
    soft = outline.buffer(-1.5, join_style='round').buffer(1.5, join_style='round')
    ring = ring_coords(soft.buffer(-0.25, join_style='round'))
    pts = resample(ring, 1.5)
    n = len(pts)
    g_lo, g_hi = 0.0, GROUND - 0.55        # first floor glass
    s_lo, s_hi = GROUND + 0.6, TOP - 1.05  # second floor glass
    u = 0.0
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        L = math.dist(a, b)
        if L < 0.05:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        rot = math.atan2(uy, ux)
        k = int(u // 1.5)
        u += L
        pale = k % 11 in (5, 6)         # a pale grey stone panel (render 3: between the shop groups)
        pier = k % 11 == 0 or k % 11 == 4
        for z0, z1 in ((g_lo, g_hi), (s_lo, s_hi)):
            if pale:
                mb.quad_wall(a, b, z0, z1, 'Stone pale')
            elif pier:
                mb.quad_wall(a, b, z0, z1, 'Stone dark')
            else:
                mb.quad_wall(a, b, z0, z1, 'Shop glass')
                mb.box(a[0], a[1], z0, 0.06, 0.12, z1 - z0, 'Shop frame', rot=rot)
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                mb.box(m[0], m[1], z1 - 0.7, L + 0.02, 0.1, 0.06, 'Shop frame', rot=rot)
                mb.box(m[0], m[1], z0, L + 0.02, 0.12, 0.1, 'Shop frame', rot=rot)
        # the dark strips under the bands (the slab edges behind the bands)
        mb.quad_wall(a, b, g_hi, GROUND - 0.35, 'Stone dark')
        mb.quad_wall(a, b, s_hi, TOP - 0.9, 'Stone dark')
    # the white bands: rounded, standing out, with a chamfered edge that catches the light
    for z0, z1, out in ((GROUND - 0.35, GROUND + 0.6, 0.9), (TOP - 0.9, TOP + 0.45, 1.3)):
        bandp = soft.buffer(out, join_style='round').difference(soft.buffer(-0.3, join_style='round'))
        mb.prism_chamfer(bandp, z0, z1, 'White band', 'White band', 'White band', c=0.06)
        # an LED line along each band at night (the night render of the tower)
        lp = ring_coords(soft.buffer(out + 0.012, join_style='round'))
        mb.ribbon(lp, z1 - 0.16, z1 - 0.08, 'Night line', closed=True)


SIGNS = ['Sign white', 'Sign warm', 'Sign blue', 'Sign green', 'Sign red']


def interior(mb, outline, tower_base, rnd, b, people):
    """Shops behind the glass: floors, ceilings with light strips, partitions, shelves, people."""
    deep = outline.buffer(-7.5, join_style='mitre')
    shell = outline.buffer(-0.15, join_style='mitre')
    zone = shell.difference(deep) if not deep.is_empty else shell
    for z0, z1 in ((0.0, GROUND), (GROUND, TOP)):
        mb.polygon_face(shell, z0 + 0.02, 'Shop floor')
        mb.polygon_face(shell, z1 - 0.45, 'Shop ceiling', up=False)
        # back wall: the shops are 7.5 m deep, then a white wall
        if not deep.is_empty:
            mb.prism(deep, z0, z1 - 0.45, 'Shop wall')
    # light strips: a rectangle of lines inside the zone, both floors
    for z in (GROUND - 0.47, TOP - 0.47):
        for d in (1.6, 4.2, 6.4):
            ring = outline.buffer(-d, join_style='mitre')
            if ring.is_empty:
                continue
            for g in getattr(ring, 'geoms', [ring]):
                cs = ring_coords(g)
                for a, c in zip(cs, cs[1:] + cs[:1]):
                    L = math.dist(a, c)
                    n = int(L // 2.4)
                    for k in range(n):
                        t = (k + 0.5) / n
                        p = (a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t)
                        mb.box(p[0], p[1], z, 1.2, 0.18, 0.02, 'Shop light', rot=math.atan2(c[1] - a[1], c[0] - a[0]), top=False, bottom=True)
    # partitions every 10-14 m along the front, shelving on them, racks and counters, people
    pts = ring_coords(shell)
    for a, c in zip(pts, pts[1:] + pts[:1]):
        L = math.dist(a, c)
        if L < 6:
            continue
        ux, uy = (c[0] - a[0]) / L, (c[1] - a[1]) / L
        nx, ny = -uy, ux   # inwards (CCW ring)
        rot = math.atan2(uy, ux)
        s = 0.0
        while s < L - 4:
            w = min(L - s, rnd.uniform(10, 14))
            p = (a[0] + ux * (s + w), a[1] + uy * (s + w))
            for z0, z1 in ((0.0, GROUND), (GROUND, TOP)):
                if s + w < L - 1:
                    mb.box(p[0] + nx * 3.7, p[1] + ny * 3.7, z0, 0.15, 7.4, z1 - z0 - 0.45, 'Shop wall', rot=rot)
                    # shelving along the partition
                    for side in (-0.45, 0.45):
                        q = (p[0] + nx * 4.0 - ux * side, p[1] + ny * 4.0 - uy * side)
                        mb.box(q[0], q[1], z0, 0.6, 5.5, 2.1, 'Shelf', rot=rot)
                        for lvl in (0.5, 1.0, 1.5):
                            mb.box(q[0], q[1], z0 + lvl, 0.5, 5.2, 0.28, rnd.choice(GOODS), rot=rot)
                # racks / tables in the middle of the shop, a counter at the back
                for k in range(rnd.randint(1, 3)):
                    t = s + rnd.uniform(2.0, w - 2.0)
                    d = rnd.uniform(2.2, 5.0)
                    q = (a[0] + ux * t + nx * d, a[1] + uy * t + ny * d)
                    kind = rnd.random()
                    if kind < 0.4:
                        mb.box(q[0], q[1], z0, 1.6, 0.8, 0.85, 'Shelf', rot=rot)
                        mb.box(q[0], q[1], z0 + 0.85, 1.4, 0.6, 0.12, rnd.choice(GOODS), rot=rot)
                    elif kind < 0.75:
                        mb.box(q[0], q[1], z0 + 1.45, 1.6, 0.05, 0.05, 'Metal', rot=rot)
                        for e in (-0.75, 0.75):
                            mb.box(q[0] + ux * e, q[1] + uy * e, z0, 0.05, 0.4, 1.5, 'Metal', rot=rot)
                        for e in range(6):
                            mb.box(q[0] + ux * (-0.6 + e * 0.24), q[1] + uy * (-0.6 + e * 0.24), z0 + 0.55, 0.08, 0.5, 0.85,
                                   rnd.choice(CLOTHES), rot=rot)
                    else:
                        mb.box(q[0], q[1], z0, 0.6, 0.6, 1.0, 'Shelf', rot=rot)
                        mb.blob(q[0], q[1], z0 + 1.35, 0.45, 0.45, 0.5, 'Leaves light', subdiv=1)
                cq = (a[0] + ux * (s + w / 2) + nx * 6.4, a[1] + uy * (s + w / 2) + ny * 6.4)
                mb.box(cq[0], cq[1], z0, 2.4, 0.7, 1.05, 'Counter', rot=rot)
                # people: a few per shop, standing or walking between the fittings
                for k in range(rnd.randint(2, 4)):
                    t = s + rnd.uniform(1.2, w - 1.2)
                    d = rnd.uniform(1.2, 5.6)
                    x, y = a[0] + ux * t + nx * d, a[1] + uy * t + ny * d
                    if zone.contains(Point(x, y)):
                        sx, sy = to_site(b, x, y)
                        people.append([round(sx, 2), round(sy, 2), round(z0 + 0.04, 2), rnd.randrange(6)])
            s += w


GOODS = ['Goods red', 'Goods blue', 'Goods yellow', 'Goods white', 'Goods green']
CLOTHES = ['Goods red', 'Goods blue', 'Goods white', 'Car dark', 'Goods yellow', 'Lounger']


def entrances(mb, b, plan, base):
    """Canopies over the residential entrances: where a stair / lift hall reaches the courtyard face."""
    common = [Polygon(c).buffer(0) for c in plan['common']]
    x0, y0, x1, y1 = base.bounds
    for c in common:
        if c.area < 20:
            continue
        cx = c.centroid.x
        # courtyard face: -y for the slab blocks (the loggia side)
        y = y0
        mb.box(cx, y - 1.4, 3.3, 4.6, 3.0, 0.22, 'Stone white', rot=0.0)
        for e in (-2.0, 2.0):
            mb.box(cx + e, y - 2.7, 0.0, 0.12, 0.12, 3.3, 'Frame dark')
        mb.box(cx, y - 0.02, 0.0, 2.2, 0.12, 2.5, 'Shop frame')
        mb.box(cx, y + 0.02, 0.05, 1.9, 0.14, 2.35, 'Shop glass')
        mb.box(cx, y - 0.08, 2.75, 3.0, 0.1, 0.4, 'Sign white')


def build_base(key, b, plan, mats, col, put, podium_site=None):
    global GROUND, SECOND, TOP, _block
    _block = b
    GROUND, SECOND, _ = config.dims(b)
    TOP = GROUND + SECOND
    rnd = random.Random(zlib.crc32(key.encode()) & 0xffff)   # (str hash() changes from run to run)
    enc = Polygon(plan['enclosure']).buffer(0)
    base = enc.buffer(-0.1, join_style='mitre')
    outline = base
    if podium_site is not None and not podium_site.is_empty:
        pod = Polygon(to_plan(b, list(podium_site.exterior.coords))).buffer(0)
        outline = unary_union([base, pod]).buffer(0.3, join_style='mitre').buffer(-0.3, join_style='mitre')
        if outline.geom_type != 'Polygon':
            outline = max(outline.geoms, key=lambda g: g.area)
    from complex.geom import ccw
    outline = ccw(outline.simplify(0.15))
    mb = MeshBuilder()
    if b['style'] == 'glass':
        glass_front(mb, outline, rnd)
    else:
        # the shop front runs straight past the small jogs of the facade line (window reveals)
        # (and past the pixel steps of the genplan's podium edge: those deviate less than 1 m)
        front = outline.buffer(0.6, join_style='mitre').buffer(-0.6, join_style='mitre').simplify(1.0)
        front = ccw(front if front.geom_type == 'Polygon' else max(front.geoms, key=lambda g: g.area))
        shop_front(mb, front, rnd, key)
    people = []
    interior(mb, outline, base, rnd, b, people)
    PEOPLE.extend(people)
    # podium roof (where it reaches beyond the tower): deck, parapet, planters
    roof = outline.difference(enc.buffer(-0.05, join_style='mitre'))
    mb.prism(outline.buffer(0.05, join_style='mitre'), TOP - 0.45, TOP, 'Stone dark', None, 'Shop ceiling')
    mb.polygon_face(roof, TOP + 0.01, 'Deck paving')
    edge = outline.exterior
    cs = list(edge.coords)
    if b['style'] == 'glass':
        rail = ring_coords(outline.buffer(-1.5, join_style='round').buffer(1.5, join_style='round').buffer(1.15, join_style='round'))
        mb.ribbon(rail, TOP + 0.45, TOP + 1.5, 'Railing glass', closed=True, double=True)
        mb.tube(rail, [TOP + 1.47] * len(rail), [TOP + 1.53] * len(rail), 0.05, 'Frame dark', closed=True)
    else:
        mb.tube(cs, [TOP] * len(cs), [TOP + 0.45] * len(cs), 0.3, 'Stone dark', closed=True)
        mb.ribbon(cs, TOP + 0.45, TOP + 1.15, 'Railing glass', closed=True, double=True)
    if roof.area > 80:
        inner = roof.buffer(-2.0)
        for g in getattr(inner, 'geoms', [inner]):
            if g.geom_type != 'Polygon' or g.area < 6:
                continue
            for p in resample(ring_coords(g.buffer(-0.5) if not g.buffer(-0.5).is_empty else g), 6.0):
                mb.box(p[0], p[1], TOP, 1.4, 1.4, 0.55, 'Planter')
                mb.blob(p[0], p[1], TOP + 0.85, 0.6, 0.6, 0.45, 'Shrub', subdiv=1)
                if rnd.random() < 0.45:
                    sx, sy = to_site(b, p[0], p[1])
                    TREES.append([round(sx, 2), round(sy, 2), TOP + 0.5, 4.5, 1.7, 'small'])
            # a few sail umbrellas and tables on the A podium terrace (render 3)
            if b['style'] == 'glass':
                for p in resample(ring_coords(g), 9.0)[::2]:
                    mb.box(p[0], p[1], TOP, 0.08, 0.08, 2.4, 'Metal')
                    mb.box(p[0], p[1], TOP + 2.35, 2.6, 2.6, 0.06, 'Umbrella sand')
                    mb.box(p[0], p[1], TOP, 0.9, 0.9, 0.75, 'Lounger')
    if b['style'] == 'brick':
        entrances(mb, b, plan, base)
    put(make_object(f'{key} shops', mb.to_mesh(f'{key} shops', mats), col))
    return outline
