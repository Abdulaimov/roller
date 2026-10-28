"""The site from the genplan (build/site_raw.json, tools/ab/site_map.py, spread: config.site_raw):
ground, kerbs, hedges, lamps, benches, car parks, the hospital (№13), the houses across the road; the
playgrounds, the six-a-side pitch, the kindergarten, the school north of the plot and the planting
(landscape.py); and the trees, cars and people the viewer draws.

Levels: roads at 0, paving +0.12, lawns +0.15 behind a kerb, play surfaces +0.13.
"""
import math
import random

import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from complex.geom import MeshBuilder, make_object, resample, ring_coords

from . import landscape as LS
from .config import SPREAD, site_raw

Z = dict(asphalt=0.0, paving=0.12, lawn=0.15, play=0.13, sport=0.13)
S = SPREAD
REGION = box(-200 * S, -110 * S, 175 * S, 135 * S)


def polys_of(raw, cls):
    out = []
    for p in raw['classes'].get(cls, []):
        g = Polygon(p['ring'], [h for h in p['holes'] if len(h) >= 3]).buffer(0)
        if not g.is_empty:
            out.append(g)
    return out


def clean(g, r=0.35, tol=0.12):
    g = g.buffer(r, join_style='round').buffer(-2 * r, join_style='round').buffer(r, join_style='round')
    return g.simplify(tol, preserve_topology=True)


def regular(g, r, tol):
    """the genplan's areas read off pixels, made into clean surfaces: slivers narrower than 2r
    taken out (opening), gaps narrower than 2r filled (closing), straight edges (simplified to tol)"""
    if g.is_empty:
        return g
    g = g.buffer(-r, join_style='mitre').buffer(r, join_style='mitre')
    g = g.buffer(r, join_style='mitre').buffer(-r, join_style='mitre')
    return g.simplify(tol, preserve_topology=True).buffer(0)


def parts(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == 'Polygon':
        return [g]
    return [q for q in getattr(g, 'geoms', []) if q.geom_type == 'Polygon']


def raised(mb, g, z, top, side='Kerb'):
    """A ground area at height z with its edge as a step down to the road."""
    for q in parts(g):
        if q.area < 0.5:
            continue
        mb.polygon_face(q, z, top)
        for ring in [q.exterior] + list(q.interiors):
            c = list(ring.coords)
            u = 0.0
            for a, b in zip(c, c[1:]):
                mb.quad_wall(a, b, -0.05, z, side, u0=u, flip=not ring.is_ccw if ring is q.exterior else ring.is_ccw)
                u += math.dist(a, b)


def kerb_line(mb, g, z, w=0.12, h=0.06, mat='Kerb'):
    for q in parts(g):
        for ring in [q.exterior] + list(q.interiors):
            c = list(ring.coords)
            if len(c) < 3:
                continue
            mb.tube(c[:-1], [z] * (len(c) - 1), [z + h] * (len(c) - 1), w, mat, closed=True)


# ----------------------------------------------------------------------------
# props
# ----------------------------------------------------------------------------

def cypress(mb, x, y, z, h, rnd):
    """a slim columnar conifer (render 3: along the podium and the shop fronts)"""
    r = h * rnd.uniform(0.11, 0.13)
    mb.box(x, y, z, 0.12, 0.12, 0.5, 'Trunk')
    mb.blob(x, y, z + 0.35 + h * 0.46, r, r, h * 0.47, 'Shrub', subdiv=2, jitter=0.05, rnd=rnd)
    mb.blob(x, y, z + 0.35 + h * 0.83, r * 0.62, r * 0.62, h * 0.16, 'Shrub', subdiv=1, jitter=0.05, rnd=rnd)


def topiary(mb, x, y, z, rnd):
    """a cloud-pruned tree: three balls of foliage stacked on a clear stem, over a round bush"""
    mb.box(x, y, z, 0.1, 0.1, 3.1, 'Trunk')
    mb.blob(x, y, z + 0.55, 0.85, 0.85, 0.55, 'Shrub', subdiv=2, jitter=0.04, rnd=rnd)
    for zz, r in ((1.55, 0.62), (2.3, 0.5), (2.95, 0.36)):
        mb.blob(x, y, z + zz, r, r, r * 0.8, 'Shrub', subdiv=2, jitter=0.04, rnd=rnd)


def mulch(mb, x, y, z, r, mat='Mulch'):
    """a round bed of bark mulch at the foot of a tree, a stone edge round it"""
    pts = [(x + r * math.cos(2 * math.pi * k / 18), y + r * math.sin(2 * math.pi * k / 18)) for k in range(18)]
    mb.polygon_face(Polygon(pts), z + 0.015, mat)
    mb.tube(pts, [z] * 18, [z + 0.05] * 18, 0.07, 'Kerb', closed=True)


def grate(mb, x, y, z, rot):
    """a cast-iron tree grate in the paving, 1.4 m square"""
    mb.box(x, y, z + 0.004, 1.4, 1.4, 0.012, 'Lamp dark', rot=rot)
    mb.box(x, y, z + 0.016, 0.6, 0.6, 0.006, 'Mulch', rot=rot)


def lamp(mb, x, y, z, h=4.5, street=False, rot=0.0):
    LS.WALK['posts'].append([x, y, 0.12])
    mb.box(x, y, z, 0.14, 0.14, h, 'Lamp dark')
    if street:
        ca, sa = math.cos(rot), math.sin(rot)
        mb.box(x + ca * 0.9, y + sa * 0.9, z + h - 0.1, 1.8, 0.12, 0.1, 'Lamp dark', rot=rot)
        mb.box(x + ca * 1.7, y + sa * 1.7, z + h - 0.22, 0.6, 0.28, 0.14, 'Lamp dark', rot=rot)
        mb.box(x + ca * 1.7, y + sa * 1.7, z + h - 0.24, 0.5, 0.22, 0.03, 'Lamp glow', rot=rot)
        hx, hy = x + ca * 1.7, y + sa * 1.7
        LS.LIGHTS.append([round(hx, 2), round(hy, 2), round(z + h - 0.25, 2), round(hx, 2), round(hy, 2), 1])
    else:
        mb.box(x, y, z + h, 0.42, 0.42, 0.08, 'Lamp dark')
        mb.box(x, y, z + h - 0.35, 0.3, 0.3, 0.35, 'Lamp glow')
        LS.LIGHTS.append([round(x, 2), round(y, 2), round(z + h - 0.18, 2), round(x, 2), round(y, 2), 0])


def bench(mb, x, y, z, rot):
    ca, sa = math.cos(rot), math.sin(rot)
    LS.WALK['solids'].append(affinity.rotate(box(x - 0.95, y - 0.3, x + 0.95, y + 0.3), rot, origin=(x, y), use_radians=True))
    mb.box(x, y, z + 0.42, 1.8, 0.45, 0.06, 'Wood', rot=rot)
    mb.box(x - sa * 0.22, y + ca * 0.22, z + 0.48, 1.8, 0.06, 0.42, 'Wood', rot=rot)
    for e in (-0.75, 0.75):
        mb.box(x + ca * e, y + sa * e, z, 0.08, 0.45, 0.42, 'Lamp dark', rot=rot)


def parking(mb, asphalt, spot, rnd, cars, blocked):
    """Bays along the asphalt edge nearest a "8" mark: 2.5 x 5 m, perpendicular, white lines; cars in most."""
    near = asphalt.intersection(Point(spot).buffer(22))
    best = None
    for q in parts(near):
        for ring in [q.exterior] + list(q.interiors):
            c = list(ring.coords)
            for a, b in zip(c, c[1:]):
                seg = LineString([a, b])
                if seg.length < 7 or seg.distance(Point(spot)) > 14:
                    continue
                if best is None or seg.length > best.length:
                    best = seg
    if best is None:
        return
    a, b = best.coords[0], best.coords[1]
    L = best.length
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    nx, ny = -uy, ux
    # inward normal: towards the asphalt
    if not asphalt.contains(Point((a[0] + b[0]) / 2 + nx * 2.5, (a[1] + b[1]) / 2 + ny * 2.5)):
        nx, ny = -nx, -ny
    n = int((L - 1) // 2.5)
    rot = math.atan2(ny, nx)
    for k in range(n + 1):
        s = 0.5 + k * 2.5
        p = (a[0] + ux * s, a[1] + uy * s)
        q = (p[0] + nx * 5.0, p[1] + ny * 5.0)
        if not asphalt.buffer(0.3).contains(LineString([p, q])):
            continue
        mb.tube([p, q], [0.005, 0.005], [0.012, 0.012], 0.1, 'Road line')
        if k < n and rnd.random() < 0.78:
            c = (p[0] + ux * 1.25 + nx * 2.6, p[1] + uy * 1.25 + ny * 2.6)
            if not any(Point(c).distance(Point(o[0], o[1])) < 2.2 for o in cars) and not blocked.contains(Point(c)):
                cars.append([round(c[0], 2), round(c[1], 2), 0.0, round(rot + (math.pi if rnd.random() < 0.5 else 0), 3), rnd.randrange(8)])


# ----------------------------------------------------------------------------
# buildings round the complex
# ----------------------------------------------------------------------------

def punched(mb, poly, z0, floors, fh, wall, glass='Window glass', bay=3.0, win=1.6, sill=0.9, wh=1.6, frame='Frame light'):
    """Plain walls with punched windows (neighbours: school, hospital, kindergarten)."""
    pts = ring_coords(poly)
    for a, b in zip(pts, pts[1:] + pts[:1]):
        L = math.dist(a, b)
        if L < 0.5:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        nx, ny = uy, -ux
        rot = math.atan2(uy, ux)
        mb.quad_wall(a, b, z0, z0 + floors * fh, wall)
        nb = int(L // bay)
        if nb < 1:
            continue
        off = (L - nb * bay) / 2
        for f in range(floors):
            for k in range(nb):
                s = off + (k + 0.5) * bay
                c = (a[0] + ux * s + nx * 0.02, a[1] + uy * s + ny * 0.02)
                zz = z0 + f * fh + sill
                mb.box(c[0], c[1], zz - 0.05, win + 0.1, 0.06, wh + 0.1, frame, rot=rot)
                mb.box(c[0] + nx * 0.02, c[1] + ny * 0.02, zz, win, 0.06, wh, glass, rot=rot)


def flat_roof(mb, poly, z, parapet='Stone white'):
    mb.polygon_face(poly.buffer(-0.3), z + 0.05, 'Roof')
    ring = poly.buffer(0.1, join_style='mitre').difference(poly.buffer(-0.3, join_style='mitre'))
    mb.prism(ring, z, z + 0.9, parapet, parapet)


def hospital(mb, poly, labels):
    """№13 on the genplan: a five-storey hospital."""
    r = poly.minimum_rotated_rectangle
    floors, fh = 5, 3.6
    punched(mb, r, 0.0, floors, fh, 'Hospital wall', bay=2.6, win=1.7, wh=1.8)
    flat_roof(mb, r, floors * fh, 'Hospital wall')
    # blue bands at the floor slabs, an entrance canopy, the sign and a red cross on the roof
    ring = r.buffer(0.15, join_style='mitre').difference(r.buffer(-0.05, join_style='mitre'))
    for f in range(1, floors):
        mb.prism(ring, f * fh - 0.15, f * fh + 0.25, 'Hospital accent', 'Hospital accent')
    c = list(r.exterior.coords)
    edges = sorted([(math.dist(c[i], c[i + 1]), i) for i in range(4)])
    L, i = edges[-1]
    a, b = c[i], c[i + 1]
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    nx, ny = uy, -ux
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    rot = math.atan2(uy, ux)
    mb.box(m[0] + nx * 2.5, m[1] + ny * 2.5, 3.6, 9.0, 5.0, 0.3, 'Stone white', rot=rot)
    mb.box(m[0] + nx * 0.3, m[1] + ny * 0.3, floors * fh + 0.9, 12.0, 0.25, 1.6, 'Hospital accent', rot=rot)
    cr = (m[0] + ux * 9 + nx * 0.4, m[1] + uy * 9 + ny * 0.4)
    mb.box(cr[0], cr[1], floors * fh + 0.9, 1.8, 0.3, 0.6, 'Sign red', rot=rot)
    mb.box(cr[0], cr[1], floors * fh + 0.6, 0.6, 0.3, 1.8, 'Sign red', rot=rot)
    cc = r.centroid
    labels.append(dict(x=round(cc.x, 2), y=round(cc.y, 2), z=floors * fh + 4, ru='Больница', tj='Беморхона', kind='hospital'))


# ----------------------------------------------------------------------------
# the site
# ----------------------------------------------------------------------------

def build_site(mats, col, towers, pods):
    LS.walk_reset()
    raw = site_raw()
    rnd = random.Random(20261020)
    plot = Polygon(raw['plot']).buffer(0)
    inside = plot.buffer(6)
    footprints = [Polygon(t['outline']).buffer(0) for t in towers]
    built = unary_union(footprints + [p for p in pods.values()])

    cls = {k: [g.intersection(REGION) for g in polys_of(raw, k)] for k in raw['classes']}
    # (the genplan is read off pixels: its edges zigzag; straightened to within ~0.4 m)
    asphalt = unary_union([clean(g, 0.3, 0.4) for g in cls['asphalt']]).intersection(REGION)
    # outside the plot only the roads and the verges and pavements along them
    road_zone = asphalt.buffer(9)

    def keep(g):
        # inside the plot: everything; outside: only real verges and pavements along the roads
        # (the road hatching of the genplan leaves small slivers that are not ground at all)
        if g.intersects(inside):
            return True
        if not g.within(road_zone) or g.area < 80:
            return False
        r = g.minimum_rotated_rectangle
        c = list(r.exterior.coords)
        return min(math.dist(c[0], c[1]), math.dist(c[1], c[2])) > 1.8
    edge = plot.buffer(1.0)

    def trimmed(gs):
        # inside the plot as drawn; outside it only the verges and pavements along the roads
        ins = unary_union([g.intersection(edge) for g in gs if g.intersects(inside)])
        out = unary_union([g.difference(edge) for g in gs if keep(g)])
        out = unary_union([q for q in parts(out) if q.area > 80 and q.distance(asphalt) < 1.0])
        return unary_union([clean(ins, 0.35, 0.45), clean(out, 0.5, 0.8)])
    lawn = regular(trimmed(cls['lawn']), 0.7, 0.45)
    paving = regular(trimmed(cls['paving'] + cls['building'] + cls['podium'] + cls['kindergarten']), 0.6, 0.45)
    play = regular(unary_union([clean(g, 0.35, 0.35) for g in cls['play'] if g.intersects(inside)]), 0.5, 0.35)
    sport = unary_union([clean(g, 0.6) for g in cls['sport'] if g.intersects(inside)])
    asphalt = regular(asphalt, 1.0, 0.5)
    blue = [g for g in cls['blue'] if g.area > 30]
    # one owner per spot: sport > play > lawn > paving > asphalt
    play = play.difference(sport)
    lawn = lawn.difference(play).difference(sport)
    paving = paving.difference(lawn).difference(play).difference(sport)
    lawn = lawn.difference(built.buffer(0.5))
    asphalt = asphalt.difference(unary_union([lawn, paving, play, sport]))
    # asphalt islands inside the plot that no road reaches (outlines of the genplan's symbols): paving
    islands = [q for q in parts(asphalt) if q.area < 260 and q.within(plot.buffer(2))]
    if islands:
        paving = unary_union([paving] + [q.buffer(0.05) for q in islands])
        asphalt = asphalt.difference(unary_union(islands).buffer(0.05))
    # south of the avenue (the genplan's neighbouring quarter: red earthwork hatching, symbols,
    # lettering that read as odd paving shapes): a 4 m pavement along the avenue, lawn beyond it,
    # the side roads kept; nothing else drawn there (a visual assumption, the genplan shows no
    # landscaping outside the plot)
    ys = lambda x: S * (-81.1 - 0.103 * (x / S + 80.0))        # the avenue's south kerb (fitted on the genplan)
    south = Polygon([(-200 * S, ys(-200 * S) - 0.3), (176 * S, ys(176 * S) - 0.3), (176 * S, -111 * S), (-200 * S, -111 * S)]).difference(plot.buffer(2))
    walk_s = south.intersection(LineString([(-110 * S, ys(-110 * S)), (176 * S, ys(176 * S))]).buffer(4.3, cap_style='flat').buffer(0))
    # the side roads (wide asphalt running off the avenue): straightened, the slivers between them gone
    side = [regular(q, 2.0, 0.6) for q in parts(asphalt.intersection(south)) if q.area > 150 and q.buffer(-2.5).area > 20]
    side = [q for q in side if not q.is_empty]
    asphalt = unary_union([asphalt.difference(south)] + side)
    lawn = unary_union([lawn.difference(south), south.difference(unary_union(side + [walk_s])).intersection(REGION)])
    paving = unary_union([paving.difference(south), walk_s.difference(unary_union(side))])
    play = play.difference(south)
    blue = [g for g in blue if not g.intersects(south)]
    # asphalt slivers left between the verges (thinner than 1.2 m): kerb-side paving
    thin = asphalt.difference(regular(asphalt, 0.6, 0.3))
    asphalt = regular(asphalt, 0.6, 0.3)
    # the gaps the classes leave between them inside the region (narrower than 2 m): the paving
    # next to them, not bare ground; and the thin asphalt slivers likewise
    filled = unary_union([asphalt, lawn, paving, play, sport])
    gaps = REGION.buffer(-0.6).difference(filled)
    small = [q for q in parts(gaps) if q.area < 40 or q.buffer(-1.0).is_empty]
    small += [q for q in parts(thin) if q.area > 0.05]
    # a gap ringed by lawn is lawn (a symbol drawn on the grass), else the paving next to it
    to_lawn, to_pav = [], []
    for q in small:
        rim = q.buffer(0.4).difference(q)
        (to_lawn if rim.area > 0 and rim.intersection(lawn).area > 0.6 * rim.area else to_pav).append(q)
    if to_lawn:
        lawn = unary_union([lawn] + [q.buffer(0.03) for q in to_lawn])
    if to_pav:
        paving = unary_union([paving] + [q.buffer(0.03) for q in to_pav]).difference(unary_union([lawn, play, sport]))
    asphalt = asphalt.difference(unary_union([paving, lawn]))

    # small islands of asphalt on their own (symbols on the genplan's lawns and paving): what is
    # round them
    keep_a = []
    for q in parts(asphalt):
        if q.area >= 150:
            keep_a.append(q)
            continue
        rim = q.buffer(0.5).difference(q)
        on_road = rim.intersection(asphalt.difference(q.buffer(0.01))).area > 0.3 * rim.area
        if on_road:
            keep_a.append(q)
        elif rim.intersection(paving).area > 0.5 * rim.area:
            paving = unary_union([paving, q.buffer(0.03)])
        else:
            lawn = unary_union([lawn, q.buffer(0.03)])   # on the lawn or the open ground
    asphalt = unary_union(keep_a)
    # small lawn islands standing on their own in the open ground (no path or road at them): ground
    lawn = unary_union([q for q in parts(lawn) if q.area >= 200 or q.buffer(0.6).intersects(unary_union([paving, asphalt, play, built]))])
    # holes in the lawns (the genplan's symbols drawn on them: arrows, letters): lawn
    def filled(g, amax):
        out = []
        for q in parts(g):
            out.append(Polygon(q.exterior, [h for h in q.interiors if Polygon(h).area >= amax]))
        return unary_union(out)
    lawn = filled(lawn, 60.0).difference(unary_union([paving, play, sport, asphalt]).buffer(0.01))
    # stray bits of paving on their own (corners of the genplan's lettering and symbols): lawn
    keep_pav, stray = [], []
    for q in parts(paving):
        others = paving.difference(q.buffer(0.01))
        touches = q.buffer(0.6).intersects(unary_union([asphalt, others, built]))
        (keep_pav if q.area >= 60 or touches else stray).append(q)
    if stray:
        paving = unary_union(keep_pav)
        lawn = unary_union([lawn] + [q.intersection(REGION) for q in stray])
    # the school's ground north of the plot and the six-a-side pitch at №14 (landscape.py): the
    # genplan's surfaces are cleared off them, they bring their own
    wings = [Polygon(p).buffer(0) for p in raw.get('kinder', [])] or [g for g in cls['kindergarten'] if g.area > 150]
    school_ground = LS.school_grounds(plot)
    blue_small = [g for g in blue if g.within(plot.buffer(1)) and g.area <= 400]
    hard = unary_union([asphalt, built] + blue_small + wings)
    keep_off = unary_union([hard, play])
    pitch_fit = LS.fit_pitch(sport, plot, hard, play) if not sport.is_empty else None
    if pitch_fit:
        print('six-a-side pitch: %.0f x %.0f m' % (pitch_fit[1], pitch_fit[2]))
    cu = unary_union([school_ground.buffer(0.5)] + ([pitch_fit[3].buffer(0.25)] if pitch_fit else []))
    lawn, paving, asphalt = (g.difference(cu) for g in (lawn, paving, asphalt))
    # (the playground next to the pitch gives way to it: its edge a metre off the fence)
    play = play.difference(school_ground.buffer(0.5))
    if pitch_fit:
        play = unary_union([q for q in parts(play.difference(pitch_fit[3].buffer(1.2))) if q.area > 4])
        keep_off = unary_union([hard, play])
    sport = Polygon()
    # (the genplan's arrows and letters on the lawns left as small holes with a kerb round them:
    # filled once more, after all the cutting above)
    lawn = filled(lawn, 60.0).difference(unary_union([paving, play, asphalt]).buffer(0.01))
    # (and such a symbol drawn as a lawn of its own by the plot's edge: a 5 m2 triangle with a kerb)
    lawn = unary_union([q for q in parts(lawn) if q.area >= 12 or q.intersects(plot.buffer(-1.0))])
    mb = MeshBuilder()
    # ground far and wide: dry grass and dust, the roads on it
    mb.polygon_face(box(-1500, -1500, 1500, 1500).difference(REGION.buffer(-0.5)), -0.06, 'Ground')
    mb.polygon_face(REGION.buffer(-0.5).difference(unary_union([asphalt, lawn, paving, play, sport]).buffer(0.05)), -0.04, 'Ground')
    for q in parts(asphalt):
        mb.polygon_face(q, 0.0, 'Asphalt')
    raised(mb, paving.buffer(0.05), Z['paving'], 'Paving', 'Kerb')
    raised(mb, lawn, Z['lawn'], 'Lawn', 'Kerb')
    kerb_line(mb, lawn, Z['lawn'] - 0.02, 0.12, 0.08)
    for i, q in enumerate(parts(play)):
        raised(mb, q, Z['play'], 'Rubber orange' if i % 2 == 0 else 'Rubber yellow', 'Kerb')
    sm = mb.to_mesh('Ground', mats)
    make_object('Ground', sm, col)

    mb = MeshBuilder()
    labels, cars, people, trees = [], [], [], []
    # playgrounds (full of play equipment) and the six-a-side pitch
    for q in parts(play):
        if q.area >= 8:
            LS.playground(mb, q, Z['play'], rnd, people)
    pitch_trees = LS.mini_pitch(mb, pitch_fit, plot, keep_off, rnd, people) if pitch_fit else []
    # kindergarten (the genplan's three wings, three storeys), its groups' verandas (the small dark
    # red rectangles drawn round it), hospital, ramps to the underground car park, substation
    kinder = LS.kindergarten(mb, wings, labels, rnd)
    if kinder is not None:
        for g in polys_of(raw, 'building'):
            # (compact rectangles of 20-90 m2 away from the plot's red edge line, which reads as
            # the same dark red)
            r = g.minimum_rotated_rectangle
            cs = list(r.exterior.coords)
            longest = max(math.dist(cs[0], cs[1]), math.dist(cs[1], cs[2]))
            if (20 < g.area < 90 and g.area > 0.7 * r.area and longest < 12 and g.distance(kinder) < 45
                    and g.distance(plot.exterior) > 5 and not g.intersects(built.buffer(1))):
                LS.veranda(mb, g, rnd)
    hosp = [g for g in blue if Point(116.6 * S, -13.2 * S).distance(g) < 5]
    for g in hosp:
        hospital(mb, g, labels)
    for g in blue:
        if g in hosp or not g.within(plot.buffer(1)) or g.area > 400:
            continue
        r = g.minimum_rotated_rectangle
        mb.polygon_face(r, 0.02, 'Asphalt')
        ring = r.buffer(0.25, join_style='mitre').difference(r)
        mb.prism(ring, 0.0, 1.1, 'Stone white', 'Stone white')
        mb.prism(r.buffer(0.3, join_style='mitre'), 2.9, 3.05, 'Frame dark', 'Shop glass', 'Frame dark')
    for w in raw['words']:
        if w['t'] in ('ПС', '6'):
            x, y = w['p']
            mb.box(x, y, 0.0, 9.0 if w['t'] == 'ПС' else 5.0, 6.0 if w['t'] == 'ПС' else 4.0, 3.2, 'Stone white', rot=math.radians(27.5))
    school_fp, school_trees = LS.school(mb, labels, plot, rnd, people)

    # houses across the roads (existing, "12"): plain five-storey blocks with drawn-on windows
    houses = []
    for g in polys_of(raw, 'podium') + polys_of(raw, 'building'):
        if g.intersects(inside) or g.area < 120:
            continue
        r = g.minimum_rotated_rectangle
        if r.area > 2500 or r.intersects(asphalt.buffer(2)):
            continue
        houses.append(r)
    paints = ['Neighbour cream', 'Neighbour peach', 'Neighbour blue', 'Neighbour solid', 'Neighbour mint', 'Neighbour rose']
    for i, r in enumerate(houses):
        mb.prism(r, 0.0, 15.0, paints[i % len(paints)], 'Roof')

    # lamps along the paths and the roads, benches by the lawns (kept apart: one lamp per 15 m,
    # one bench per 9 m, whatever the outlines of the paved areas)
    lamps, benches = [], []

    def spaced(lst, p, gap):
        if any(math.dist(p, q) < gap for q in lst):
            return False
        lst.append(p)
        return True
    for q in parts(paving.intersection(inside)):
        if q.area < 60:
            continue
        for p in resample(ring_coords(q.buffer(-0.6)) if not q.buffer(-0.6).is_empty and q.buffer(-0.6).geom_type == 'Polygon' else ring_coords(q), 17.0):
            if built.buffer(2.5).contains(Point(p)) or not spaced(lamps, p, 15.0):
                continue
            lamp(mb, p[0], p[1], Z['paving'], 4.2)
    # A bench stands on the paving at a lawn's edge, its back to the lawn and the seat facing the
    # path (whichever way the lawn's outline runs: 22.10.2026 some faced the lawn, half on the kerb),
    # wholly on the paving with 1.5 m clear in front of it (no bench where the path is too narrow
    # for it and people to pass), off the lamps; the trees, plantings and people come after it and
    # keep clear of it (BENCH_ZONES)
    seats, seat_zones = [], []
    # what stands already: play equipment, verandas, the school and the pitch, their fences, posts and trees
    standing = unary_union([g.buffer(0.3) for g in LS.WALK['solids']]
                           + [LineString(cc).buffer(wd / 2 + 0.3) for wd, cc in LS.WALK['lines'] if len(cc) > 1]
                           + [Point(x, y).buffer(r + 0.4) for x, y, r in LS.WALK['posts']]
                           + [Point(t[0], t[1]).buffer(1.2) for t in school_trees + pitch_trees])
    for q in parts(lawn.intersection(inside)):
        if q.area < 40:
            continue
        ring = ring_coords(q)
        for i, p in enumerate(resample(ring, 23.0)):
            pp = Point(p)
            if paving.distance(pp) > 0.6 or built.buffer(4).contains(pp) or any(math.dist(p, b) < 9.0 for b in benches):
                continue
            s = q.exterior.project(pp)
            a, b = q.exterior.interpolate(s - 0.6), q.exterior.interpolate(s + 0.6)
            rot = math.atan2(b.y - a.y, b.x - a.x)
            n = (math.sin(rot), -math.cos(rot))  # the way the sitter faces (bench(): back on the other side)
            if not paving.contains(Point(p[0] + n[0] * 1.5, p[1] + n[1] * 1.5)):
                rot += math.pi
                n = (-n[0], -n[1])
            c = (p[0] + n[0] * 0.65, p[1] + n[1] * 0.65)
            seat = affinity.rotate(box(c[0] - 0.95, c[1] - 0.3, c[0] + 0.95, c[1] + 0.3), rot, origin=c, use_radians=True)
            front = affinity.rotate(box(c[0] - 0.95, c[1] - 1.8, c[0] + 0.95, c[1] - 0.3), rot, origin=c, use_radians=True)
            if (not paving.buffer(-0.05).contains(seat) or not paving.buffer(-0.05).contains(front)
                    or any(math.dist(c, l) < 1.6 for l in lamps) or standing.intersects(seat.union(front))):
                continue
            benches.append(p)
            seats.append((c, rot, seat))
            seat_zones.append((seat, front))
            bench(mb, c[0], c[1], Z['paving'], rot)
    BENCH_ZONES = unary_union([g.buffer(1.4) for _, _, g in seats]) if seats else Polygon()
    print(f'benches by the lawns: {len(seats)}')
    # street lamps: along the road edges outside the plot, every 30 m
    verge = unary_union([lawn, paving])
    for q in parts(asphalt):
        if q.area < 2000:
            continue
        ext = q.exterior if q.exterior.is_ccw else LineString(list(q.exterior.coords)[::-1])
        for p in resample(list(ext.coords)[:-1], 32.0):
            pp = Point(p)
            if inside.buffer(-4).contains(pp) or verge.distance(pp) > 1.0 or not spaced(lamps, p, 24.0):
                continue
            n = ext.interpolate(ext.project(pp) + 0.5)
            ang = math.atan2(n.y - p[1], n.x - p[0])
            rot = ang + math.pi / 2  # into the road (CCW ring: road on the left)
            lamp(mb, p[0] - math.cos(rot) * 0.7, p[1] - math.sin(rot) * 0.7, 0.12, 9.0, street=True, rot=rot)

    # hedges along the plot edge facing the roads
    edge = plot.exterior
    for q in parts(lawn.intersection(plot.difference(plot.buffer(-6)))):
        if q.area < 20:
            continue
        line = q.exterior.intersection(edge.buffer(4))
        for l in getattr(line, 'geoms', [line]):
            if l.geom_type != 'LineString' or l.length < 3:
                continue
            c = list(l.coords)
            LS.WALK['lines'].append([0.8, c])
            mb.tube(c, [Z['lawn']] * len(c), [Z['lawn'] + 0.9] * len(c), 0.8, 'Shrub')

    # car parks at the "8" marks
    blocked = unary_union([built, lawn, play, paving]).buffer(0.2)
    for w in raw['words']:
        if w['t'] == '8' and REGION.contains(Point(w['p'])):
            parking(mb, asphalt, w['p'], rnd, cars, blocked)
    # cars on the roads outside the plot: in the lanes, along the road
    road = asphalt.difference(inside)
    core = road.buffer(-3.2)
    for q in parts(core):
        x0, y0, x1, y1 = q.bounds
        n = int(q.area / 140)
        for k in range(n):
            p = Point(rnd.uniform(x0, x1), rnd.uniform(y0, y1))
            if not q.contains(p) or any(p.distance(Point(c[0], c[1])) < 9 for c in cars):
                continue
            # direction of the road here: the longer side of the local asphalt's rotated rectangle
            loc = road.intersection(p.buffer(14)).minimum_rotated_rectangle
            cc = list(loc.exterior.coords)
            e1 = (cc[1][0] - cc[0][0], cc[1][1] - cc[0][1])
            e2 = (cc[2][0] - cc[1][0], cc[2][1] - cc[1][1])
            e = e1 if math.hypot(*e1) >= math.hypot(*e2) else e2
            rot = math.atan2(e[1], e[0]) + (math.pi if rnd.random() < 0.5 else 0)
            cars.append([round(p.x, 2), round(p.y, 2), 0.0, round(rot, 3), rnd.randrange(8)])

    # trees: the school's and the pitch's, the genplan's, then lawns filled in, then street trees
    # along the verges (none on the pitch, the playgrounds or by the kindergarten's walls)
    trees += school_trees + pitch_trees
    no_trees = unary_union([built.buffer(3.5), school_fp.buffer(2), play.buffer(0.6), BENCH_ZONES.buffer(0.4)]
                           + ([pitch_fit[3].buffer(2.5)] if pitch_fit else []) + ([kinder.buffer(3.0)] if kinder is not None else []))

    def free(p, gap):
        return (not no_trees.contains(p) and all(p.distance(Point(t[0], t[1])) >= gap for t in trees)
                and all(p.distance(Point(l)) >= 1.8 for l in lamps))
    for x, y in raw['trees']:
        p = Point(x, y)
        if REGION.contains(p) and free(p, 2.5):
            trees.append([x, y, Z['lawn'], round(rnd.uniform(6.5, 9.5), 2), round(rnd.uniform(2.4, 3.4), 2), 'broad'])
    for q in parts(lawn):
        if q.area < 25:
            continue
        inner = q.buffer(-1.6)
        if inner.is_empty:
            continue
        x0, y0, x1, y1 = inner.bounds
        target = int(q.area / (75 if q.intersects(inside) else 110))
        tries = 0
        placed = 0
        while placed < target and tries < target * 30:
            tries += 1
            p = Point(rnd.uniform(x0, x1), rnd.uniform(y0, y1))
            if not inner.contains(p) or not free(p, 6.0):
                continue
            r = rnd.random()
            kind = 'conifer' if r < 0.18 else 'poplar' if r < 0.3 else 'small' if r < 0.45 else 'broad'
            h = {'conifer': (7, 11), 'poplar': (9, 14), 'small': (3.5, 5.5), 'broad': (6, 10)}[kind]
            trees.append([round(p.x, 2), round(p.y, 2), Z['lawn'], round(rnd.uniform(*h), 2), round(rnd.uniform(1.8, 3.4), 2), kind])
            placed += 1
    # planting along the street fronts (render 3): columnar conifers and cloud-pruned trees in turn,
    # 5-6 m out from the shop fronts, on the lawn verges or the paving (not on the roads, kept
    # clear of the lamps, the trees and the entrances)
    from .config import BLOCKS
    from .towers import frame as block_frame
    planted = []
    soft_ground = unary_union([lawn, paving]).difference(built.buffer(3.0))

    def free_spot(p, gap=3.2):
        return (soft_ground.contains(p) and not BENCH_ZONES.contains(p) and all(p.distance(Point(t[0], t[1])) > gap for t in trees)
                and all(p.distance(Point(q)) > 2.0 for q in lamps) and all(p.distance(q) > gap for q in planted))
    for key, side in (('B', 'y'), ('V', 'y'), ('G', 'y'), ('D', 'y'), ('A', '-y'), ('A', '-x')):
        b = BLOCKS[key]
        ang, to_site = block_frame(b)
        ca, sa = math.cos(ang), math.sin(ang)
        cx, cy = b['centre']
        pod = pods.get(key)
        fp = unary_union([Polygon([((ca * (x - cx) + sa * (y - cy)), (-sa * (x - cx) + ca * (y - cy))) for x, y in g.exterior.coords])
                          for g in parts(unary_union([pod] if pod is not None else []))] + [Polygon([((ca * (x - cx) + sa * (y - cy)), (-sa * (x - cx) + ca * (y - cy))) for x, y in Polygon(next(t for t in towers if t['key'] == key)['outline']).exterior.coords])])
        x0, y0, x1, y1 = fp.bounds
        if side == 'y':
            line = [(x, y1 + 5.5) for x in [x0 + 4 + 9.0 * k for k in range(int((x1 - x0 - 8) / 9.0) + 1)]]
        elif side == '-y':
            line = [(x, y0 - 5.0) for x in [x0 + 4 + 9.0 * k for k in range(int((x1 - x0 - 8) / 9.0) + 1)]]
        else:
            line = [(x0 - 5.0, y) for y in [y0 + 4 + 9.0 * k for k in range(int((y1 - y0 - 8) / 9.0) + 1)]]
        for i, (px, py) in enumerate(line):
            sx, sy = to_site(px, py)
            p = Point(sx, sy)
            if not free_spot(p):
                continue
            zg = Z['lawn'] if lawn.contains(p) else Z['paving']
            if i % 2 == 0:
                # (22.10.2026) a photographed columnar conifer (the viewer's tree atlases) instead of
                # the smooth modelled column, which read as plastic close up
                trees.append([round(sx, 2), round(sy, 2), zg, round(rnd.uniform(5.5, 7.0), 2), 0.95, 'poplar'])
            else:
                topiary(mb, sx, sy, zg, rnd)
                # (the conifers get their bed with the other trees' below)
                if zg == Z['lawn']:
                    mulch(mb, sx, sy, zg, 1.0)
                else:
                    grate(mb, sx, sy, zg, ang)
            planted.append(p)
    # beds under the trees: mulch on the lawns, grates in the paving (inside the plot)
    for t in trees:
        p = Point(t[0], t[1])
        if not inside.contains(p) or t[2] > 1.0:
            continue
        if lawn.buffer(-0.6).contains(p):
            mulch(mb, t[0], t[1], Z['lawn'], min(1.3, 0.45 * t[4] + 0.35))
        elif paving.buffer(-0.8).contains(p):
            grate(mb, t[0], t[1], Z['paving'], 0.47)
    # shrub groups and flower beds on the lawns
    avoid = unary_union([Point(t[0], t[1]).buffer(max(1.2, t[4] * 0.6)) for t in trees] + [play.buffer(1.0), no_trees, BENCH_ZONES]
                        + [Point(l).buffer(1.2) for l in lamps])
    trees += LS.plantings(mb, lawn.intersection(inside), avoid, rnd, Z['lawn'])
    # people on the paths and plazas: not on a bench's seat or in its way, not in a lamp, a tree's
    # grate or a planting
    taken = unary_union([BENCH_ZONES.buffer(-0.6)]
                        + [Point(l).buffer(0.6) for l in lamps]
                        + [Point(t[0], t[1]).buffer(1.0) for t in trees if t[2] < 1.0]
                        + [q.buffer(1.0) for q in planted])
    walk = paving.intersection(inside).difference(built.buffer(1.0)).difference(taken)
    x0, y0, x1, y1 = walk.bounds
    n = 0
    while n < 140:
        p = Point(rnd.uniform(x0, x1), rnd.uniform(y0, y1))
        if walk.contains(p):
            people.append([round(p.x, 2), round(p.y, 2), Z['paving'], rnd.randrange(6)])
            n += 1
    # nobody inside a building, a car, a bench, play equipment or a veranda (the playgrounds', the
    # pitch's and the school's people were placed before some of these stood)
    occupied = unary_union([g.buffer(0.35) for g in LS.WALK['solids']]
                           + [affinity.rotate(box(x - 2.6, y - 1.2, x + 2.6, y + 1.2), r, origin=(x, y), use_radians=True) for x, y, _, r, _ in cars]
                           + [Point(l).buffer(0.6) for l in lamps]
                           + [Point(t[0], t[1]).buffer(0.8) for t in trees if t[2] < 1.0]
                           + ([kinder.buffer(0.4)] if kinder is not None else []) + [g.buffer(0.4) for g in hosp] + [r.buffer(0.4) for r in houses]
                           + [g.minimum_rotated_rectangle.buffer(0.6) for g in blue if g.area <= 400]
                           + [seat.union(front).buffer(0.4) for seat, front in seat_zones])
    shapely.prepare(occupied)
    before = len(people)
    people[:] = [p for p in people if p[2] >= 1.0 or not occupied.contains(Point(p[0], p[1]))]
    print(f'people: {len(people)} ({before - len(people)} taken out of buildings, cars, benches and equipment)')
    for t in towers:
        c = Polygon(t['outline']).centroid
        labels.append(dict(x=round(c.x, 2), y=round(c.y, 2), z=t['top'] + 9, ru=t['label'], tj=t['tj'], kind='block', key=t['key']))

    om = mb.to_mesh('Site props', mats)
    make_object('Site props', om, col)
    walk = walk_map(towers, built, kinder, plot, asphalt, paving, lawn, play, blue, hosp, raw, houses, trees, planted, cars, people, school_fp)
    return dict(trees=trees, cars=cars, people=people, labels=labels, walk=walk, lamps=[list(l) for l in LS.LIGHTS],
                benches=[[round(c[0], 2), round(c[1], 2), round(r, 3)] for c, r, _ in seats])


def lawn_mask(lawn, W, x0, y0, nx, ny, step=0.25):
    """where the lawns are, finer than the ground grid (the viewer's grass grows only there, never on a
    kerb or the paving): a step x step m grid, run lengths along the rows (out, in, out...) as LEB128"""
    import base64
    import numpy as np
    import shapely
    g = unary_union([lawn] + [geom for k, geom in W['surf'] if k == 'school_lawn']).buffer(-0.12)
    shapely.prepare(g)
    gx, gy = int(round(nx / step)), int(round(ny / step))
    X, Y = np.meshgrid(x0 + (np.arange(gx) + 0.5) * step, y0 + (np.arange(gy) + 0.5) * step)
    flat = shapely.contains_xy(g, X, Y).ravel()
    cuts = np.concatenate([[0], np.flatnonzero(np.diff(flat.astype(np.int8))) + 1, [flat.size]])
    runs = ([0] if flat[0] else []) + np.diff(cuts).tolist()
    leb = bytearray()
    for v in runs:
        while True:
            b, v = v & 0x7F, v >> 7
            leb.append(b | (0x80 if v else 0))
            if not v:
                break
    return dict(step=step, gx=gx, gy=gy, runs=base64.b64encode(bytes(leb)).decode())


def walk_map(towers, built, kinder, plot, asphalt, paving, lawn, play, blue, hosp, raw, houses, trees, planted, cars, people, school_ground):
    """The ground for walking on (src/sitewalk.js), site metres: what is underfoot on a 1 m grid
    (kinds: 0 no way, 1 asphalt, 2 paving, 3 lawn, 4 play surface, 5 pitch, 6 school lawn,
    7 school paving, 8 track, 9 bare ground), the outlines one cannot walk through (buildings, play
    equipment, benches, cars...), fences and hedges as lines, masts, lamps and trunks as posts, and
    where the walk begins (the courtyard entrance between blocks Б and В, and one at each block)."""
    import base64
    import numpy as np
    import shapely
    W = LS.WALK
    R1 = lambda v: round(float(v), 2)
    ring = lambda g, tol=0.05: [[R1(x), R1(y)] for x, y in list(g.simplify(tol, preserve_topology=True).exterior.coords)[:-1]]
    solids = []
    def solid(g, tol=0.05):
        for q in parts(g):
            if q.area > 0.05:
                solids.append(ring(q, tol))
    solid(built.buffer(0.35, join_style='mitre'), 0.1)   # shop windows: a step back from the glass
    if kinder is not None:
        solid(kinder.buffer(0.2, join_style='mitre'))
    for g in hosp:
        solid(g.minimum_rotated_rectangle.buffer(0.3, join_style='mitre'))
    for g in blue:
        if g in hosp or not g.within(plot.buffer(1)) or g.area > 400:
            continue
        solid(g.minimum_rotated_rectangle.buffer(0.35, join_style='mitre'))
    for w in raw['words']:
        if w['t'] in ('ПС', '6'):
            x, y = w['p']
            sx, sy = (9.0, 6.0) if w['t'] == 'ПС' else (5.0, 4.0)
            solid(affinity.rotate(box(x - sx / 2, y - sy / 2, x + sx / 2, y + sy / 2), 27.5, origin=(x, y)))
    for r in houses:
        solid(r)
    for g in W['solids']:
        solid(g)
    for c in cars:
        x, y, _, rot, _ = c
        solid(affinity.rotate(box(x - 2.35, y - 0.98, x + 2.35, y + 0.98), rot, origin=(x, y), use_radians=True))
    posts = [[R1(x), R1(y), R1(r)] for x, y, r in W['posts']]
    for t in trees:
        x, y, z, h, rr, kind = t
        if z > 1.0:
            continue   # on a podium deck
        r = max(0.3, min(0.8, rr * 0.55)) if kind == 'shrub' else 0.28 if kind in ('broad', 'full', 'small') else 0.35
        posts.append([R1(x), R1(y), R1(r)])
    for p in planted:
        posts.append([R1(p.x), R1(p.y), 0.45])
    for pe in people:
        if pe[2] < 1.0:
            posts.append([R1(pe[0]), R1(pe[1]), 0.28])
    lines = [[R1(w), [[R1(x), R1(y)] for x, y in c]] for w, c in W['lines']]
    # what is underfoot, 1 m grid over the walkable area
    area = unary_union([REGION, school_ground]).buffer(0)
    x0, y0, x1, y1 = [math.floor(v) for v in area.bounds[:2]] + [math.ceil(v) for v in area.bounds[2:]]
    nx, ny = x1 - x0, y1 - y0
    X, Y = np.meshgrid(np.arange(nx) + x0 + 0.5, np.arange(ny) + y0 + 0.5)
    grid = np.zeros((ny, nx), np.uint8)
    def paint(kind, g):
        if g is None or g.is_empty:
            return
        shapely.prepare(g)
        m = shapely.contains_xy(g, X, Y)
        grid[m] = kind
    paint(9, area)
    paint(1, asphalt)
    paint(2, paving)
    paint(3, lawn)
    paint(4, play)
    surf = {'school_lawn': 6, 'school_paving': 7, 'track': 8, 'pitch': 5}
    for name in ('school_lawn', 'school_paving', 'track', 'pitch'):
        for k, g in W['surf']:
            if k == name:
                paint(surf[k], g)
    # where the walker can get to: a 0.4 m grid of the points a shoulder clear of everything (as
    # src/sitewalk.js tests a point), only the part joined to the courtyard, no pockets between a
    # trunk and a fence; for the search of the way to a clicked point and the ring under the pointer
    G, RW = 0.4, 0.3
    gx, gy = math.ceil(round(nx / G, 6)), math.ceil(round(ny / G, 6))
    CX, CY = np.meshgrid(x0 + (np.arange(gx) + 0.5) * G, y0 + (np.arange(gy) + 0.5) * G)
    ci, cj = np.floor(CX - x0).astype(int), np.floor(CY - y0).astype(int)
    on = (ci < nx) & (cj < ny)
    on[on] = grid[cj[on], ci[on]] != 0
    block = unary_union([Polygon(sr).buffer(RW - 0.02) for sr in solids]
                        + [LineString(c).buffer(RW + w / 2 - 0.02) for w, c in lines if len(c) > 1]
                        + [Point(x, y).buffer(RW + r - 0.02, quad_segs=16) for x, y, r in posts])
    shapely.prepare(block)
    roomy = on & ~shapely.contains_xy(block, CX, CY)
    # the parts joined side to side: runs along each row, joined where they overlap the row below
    rows = []
    for j in range(gy):
        d = np.diff(np.concatenate([[0], roomy[j].astype(np.int8), [0]]))
        rows.append(list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist())))
    up = {}
    def find(a):
        while up.get(a, a) != a:
            up[a] = up.get(up[a], up[a])
            a = up[a]
        return a
    for j in range(1, gy):
        lo, hi, m = rows[j - 1], rows[j], 0
        for n, (s0, e0) in enumerate(hi):
            while m < len(lo) and lo[m][1] <= s0:
                m += 1
            k = m
            while k < len(lo) and lo[k][0] < e0:
                ra, rb = find((j, n)), find((j - 1, k))
                if ra != rb:
                    up[ra] = rb
                k += 1
    size = {}
    for j, rr in enumerate(rows):
        for n, (s0, e0) in enumerate(rr):
            r = find((j, n))
            size[r] = size.get(r, 0) + e0 - s0
    main = max(size, key=size.get)
    reach = np.zeros_like(roomy)
    for j, rr in enumerate(rows):
        for n, (s0, e0) in enumerate(rr):
            if find((j, n)) == main:
                reach[j, s0:e0] = True
    ri, rj = np.nonzero(reach.T)
    def snap(q):
        # a start point inside the reachable part (the nearest such cell if it fell in a pocket)
        i, j = int((q.x - x0) / G), int((q.y - y0) / G)
        if reach[j, i]:
            return q
        k = np.argmin((ri - i) ** 2 + (rj - j) ** 2)
        return Point(x0 + (ri[k] + 0.5) * G, y0 + (rj[k] + 0.5) * G)
    # run lengths along the rows, alternately out of reach and in it, as LEB128 bytes
    flat = reach.ravel()
    cuts = np.concatenate([[0], np.flatnonzero(np.diff(flat.astype(np.int8))) + 1, [flat.size]])
    runs = ([0] if flat[0] else []) + np.diff(cuts).tolist()
    leb = bytearray()
    for v in runs:
        while True:
            b, v = v & 0x7F, v >> 7
            leb.append(b | (0x80 if v else 0))
            if not v:
                break
    # where the walk begins: a spot on the paving with a clear view (no trunk, lamp or bench just
    # before the eye, no other building in the way): the gap between blocks Б and В off the avenue,
    # looking into the courtyard; and 28-45 m off each block on its courtyard side, looking up at it
    from .config import BLOCKS
    P = np.array([[x, y] for x, y, _ in posts])
    kind_at = lambda x, y: grid[int(y - y0), int(x - x0)] if 0 <= x - x0 < nx and 0 <= y - y0 < ny else 0
    cand = [(x0 + (i + 0.5) * G, y0 + (j + 0.5) * G) for i, j in zip(ri[::7], rj[::7])
            if kind_at(x0 + (i + 0.5) * G, y0 + (j + 0.5) * G) in (2, 7)]
    parts_all = [Polygon(sr) for sr in solids]
    tree = shapely.STRtree(parts_all)
    def clutter(q, d, length, width=2.0):
        # trunks, lamps and people within a few metres of the line of sight, the nearer the worse
        v = P - q
        t = np.clip(v @ d, 0, length)
        off = np.hypot(*(v - t[:, None] * d).T)
        m = (off < width) & (v @ d > 0) & (np.hypot(*v.T) < length)
        return float(np.sum(1.0 / np.maximum(1.0, t[m])))
    def blocked(q, e, skip=None):
        seg = LineString([q, e])
        return any(skip is None or not parts_all[k].intersects(skip) for k in tree.query(seg, predicate='intersects'))
    bb, bv = BLOCKS['B']['centre'], BLOCKS['V']['centre']
    p0 = np.array([(bb[0] + bv[0]) / 2, (bb[1] + bv[1]) / 2 - 8.0])
    best = None
    for q in cand:
        q = np.array(q)
        dd = np.hypot(*(q - p0))
        if dd > 14 or kind_at(*q) != 2 or blocked(q, q + [0, 30.0]):
            continue
        wall = min(parts_all[k].distance(Point(q)) for k in tree.query(Point(q).buffer(8.0)) ) if len(tree.query(Point(q).buffer(8.0))) else 8.0
        sc = clutter(q, np.array([0.0, 1.0]), 30.0, 4.0) * 4 + dd * 0.05 + max(0.0, 6.0 - wall)
        if best is None or sc < best[0]:
            best = (sc, q)
    q = best[1] if best else np.array(snap(Point(*p0)).coords[0])
    spawn = dict(x=R1(q[0]), y=R1(q[1]), look=[0.0, 1.0], pitch=0.02)
    blocks = {}
    for t in towers:
        out = Polygon(t['outline'])
        c = np.array(out.centroid.coords[0])
        a = math.radians(BLOCKS[t['key']]['rot'])
        # the courtyard side of a slab block is its plan -y; tower A: towards the courtyard (east)
        side = np.array((math.sin(a), -math.cos(a)) if t['key'] != 'A' else (1.0, 0.0))
        best = None
        for q in cand:
            q = np.array(q)
            D = out.exterior.distance(Point(q))
            if not 28.0 <= D <= 45.0 or (q - c) @ side < 0.6 * np.hypot(*(q - c)):
                continue
            d = (c - q) / np.hypot(*(c - q))
            e = np.array(out.exterior.interpolate(out.exterior.project(Point(q))).coords[0])
            if blocked(q, q + d * (D - 2.0), skip=out) or blocked(q, e + (q - e) * 0.05, skip=out):
                continue
            sc = clutter(q, d, D) * 4 + abs(D - 34.0) * 0.08 + (1.0 - (q - c) @ side / np.hypot(*(q - c))) * 3
            if best is None or sc < best[0]:
                best = (sc, q, D)
        if best is None:
            q, D = np.array(snap(Point(*(c + side * 30))).coords[0]), 30.0
        else:
            _, q, D = best
        pitch = min(0.3, max(0.05, math.atan((t['top'] - 1.6) / D) - 0.62))
        blocks[t['key']] = dict(x=R1(q[0]), y=R1(q[1]), look=[R1(c[0] - q[0]), R1(c[1] - q[1])], pitch=R1(pitch))
    return dict(x0=x0, y0=y0, nx=nx, ny=ny, step=1.0, ground=base64.b64encode(grid.tobytes()).decode(),
                solids=solids, lines=lines, posts=posts, spawn=spawn, blocks=blocks,
                reach=dict(step=G, gx=gx, gy=gy, runs=base64.b64encode(bytes(leb)).decode()),
                lawn=lawn_mask(lawn, W, x0, y0, nx, ny))
