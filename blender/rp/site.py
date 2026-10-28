"""Round the complex: the two streets it stands on (кӯчаи И. Нарзиқулова along Б and В, кӯчаи
Ш. Ҳусейнзода along Б and А, with the parking bays along the pavement as on the developer's model),
the courtyard inside the L of the blocks (paved plaza, lawns with trees, a playground, two pergolas,
the drive round it), and the neighbourhood from OpenStreetMap (blender/rp/osm.json): the houses with
their storeys, the roads; across кӯчаи Ҳусейнзода the maternity hospital № 2 (Таваллудхонаи № 2,
a cream two-storey house with a four-storey wing), the school № 20 further on.

Levels: roads 0, pavements and paving +0.12, lawns +0.15 behind a kerb, play surface +0.13.
Returns what the viewer needs: trees, cars, people, lamps, benches, labels, the walk map.
"""
import base64
import json
import math
import os
import random

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from ab import landscape as LS
from ab.site import bench, lamp, lawn_mask
from complex.geom import MeshBuilder, log_tree, make_object

from .config import HERE, sheet_to_site

Z = dict(asphalt=0.0, paving=0.12, lawn=0.15, play=0.13)


def S(x, y):
    return sheet_to_site(x, y)


def SP(pts):
    return Polygon([S(x, y) for x, y in pts]).buffer(0)


def SB(x0, y0, x1, y1):
    return SP([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def parts(g):
    if g is None or g.is_empty:
        return []
    return [q for q in getattr(g, 'geoms', [g]) if q.geom_type == 'Polygon']


def raised(mb, g, z, top, side='Kerb'):
    for q in parts(g):
        if q.area > 0.05:
            mb.prism(q, 0.0, z, side, top)


def build_site(mats, col, towers, podium_o):
    rnd = random.Random(11)
    LS.walk_reset()
    mb = MeshBuilder()
    trees, cars, people, benches, labels = [], [], [], [], []
    osm = json.load(open(os.path.join(HERE, 'osm.json')))

    # ---------------- the plot and its two streets (sheet frame: x along Нарзиқулова, y along Ҳусейнзода)
    px0, py0, px1, py1 = podium_bounds(podium_o)
    # кӯчаи И. Нарзиқулова: pavement 4.5 m, parking bays 5.5 m, the road 10 m, pavement 5 m
    n_pav = (px0 - 60, py1, px1 + 60, py1 + 4.5)
    n_bay = (px0 - 6, py1 + 4.5, px1 - 2, py1 + 10.0)
    n_road = (-400, py1 + 4.5, 400, py1 + 18.0)
    n_far = (-400, py1 + 18.0, 400, py1 + 21.0)
    # кӯчаи Ш. Ҳусейнзода: the same along the east side, a wider road (12 m)
    e_pav = (px1, py0 - 60, px1 + 4.5, py1 + 4.5)
    e_bay = (px1 + 4.5, py0 + 4, px1 + 10.0, py1 - 2)
    e_road = (px1 + 4.5, -400, px1 + 22.0, 400)
    e_far = (px1 + 22.0, -400, px1 + 27.0, 400)
    roads = unary_union([SB(*n_road), SB(*e_road)])
    bays = unary_union([SB(*n_bay), SB(*e_bay)])
    # the plot: from the streets to 64 m south of Нарзиқулова's pavement, 14 m west of block В
    plot = SB(px0 - 14, py0 - 30, px1, py1)
    courtyard = plot.difference(podium_o)
    # the drive round the courtyard (west and south edges), with bays
    drive = SB(px0 - 14, py0 - 30, px0 - 8, py1).union(SB(px0 - 14, py0 - 30, px1, py0 - 24))
    drive_bays = SB(px0 - 8, py0 - 24, px0 - 2.5, py0 + 30).union(SB(px0 + 4, py0 - 24, px1 - 30, py0 - 18.5))
    yard = courtyard.difference(drive).difference(drive_bays)
    pav = unary_union([SB(*n_pav), SB(*e_pav), SB(*n_far), SB(*e_far)]).difference(roads.union(bays))
    pav = pav.union(plot.difference(drive).difference(drive_bays).difference(podium_o).intersection(podium_o.buffer(3.0)))

    # ---------------- the neighbourhood's roads (OSM), with pavements
    city_roads = []
    for r in osm['roads']:
        ln = LineString(r['line'])
        city_roads.append(ln.buffer(r['w'] / 2, cap_style='flat'))
    city_roads = unary_union(city_roads) if city_roads else Polygon()
    region = Point(0, 0).buffer(560)
    city_roads = city_roads.intersection(region).difference(plot.buffer(1))
    city_pav = city_roads.buffer(2.6).difference(city_roads).difference(plot.buffer(1)).intersection(region)
    asphalt = unary_union([roads, bays, drive, drive_bays, city_roads]).intersection(region)

    # ---------------- the neighbours' houses
    houses = []
    tones = ['Neighbour cream', 'Neighbour solid', 'Neighbour peach', 'Neighbour solid', 'Neighbour cream', 'Neighbour blue', 'Neighbour rose']
    hb = MeshBuilder()
    roddom_parts, school = [], None
    for i, bld in enumerate(osm['buildings']):
        g = Polygon(bld['ring']).buffer(0)
        if g.is_empty or not region.contains(g.centroid):
            continue
        g = g.simplify(0.3)
        if g.intersects(plot.buffer(2)):
            continue
        if g.intersects(roads):
            g = g.difference(roads.buffer(3.5))
            g = max(parts(g), key=lambda q: q.area) if parts(g) else Polygon()
            if g.area < 60:
                continue
        lv = bld['levels'] or (4 if g.area > 150 else 2)
        if 'Роддом' in str(bld.get('name')) or bld.get('amenity') == 'hospital':
            mat = 'Neighbour cream'
        else:
            mat = tones[i % len(tones)]
        h = 3.1 * lv + 0.6
        hb.prism(g, -0.3, h, mat, 'Roof')
        # a parapet and a little height on the roof
        if g.area > 80:
            hb.prism(g.exterior.buffer(0.15).intersection(g), h, h + 0.7, mat, 'Roof')
        houses.append(g)
    # the maternity hospital and the school: the houses round their OSM points
    places = {p['kind'] + ':' + p['name']: p for p in osm['places']}
    for p in osm['places']:
        pt = Point(*p['at'])
        near = [g for g in houses if g.distance(pt) < 25]
        if not near:
            continue
        top = max(3.1 * 4 + 1, 10)
        if 'Роддом' in p['name']:
            labels.append(dict(x=p['at'][0], y=p['at'][1], z=top + 4, ru='Роддом № 2', tj='Таваллудхонаи № 2', kind='hospital'))
        elif p['kind'] == 'school' and math.hypot(*p['at']) < 300:
            labels.append(dict(x=p['at'][0], y=p['at'][1], z=top + 2, ru=p['name'].replace('Средняя школа', 'Школа'), tj='Мактаби миёнаи № 20', kind='school'))
    make_object('Neighbours', hb.to_mesh('Neighbours', mats), col)

    # ---------------- ground
    base = region.difference(asphalt)
    mb.polygon_face(region.buffer(400).difference(region), -0.05, 'Ground')
    lawn_city = base.difference(city_pav).difference(pav).difference(plot).difference(unary_union(houses).buffer(0.5) if houses else Polygon())
    raised(mb, lawn_city, Z['lawn'] - 0.05, 'Lawn')
    raised(mb, city_pav.difference(asphalt), Z['paving'], 'Sidewalk')
    raised(mb, pav, Z['paving'], 'Paving')
    mb.polygon_face(asphalt, 0.0, 'Asphalt')
    # road markings: the centre lines of the two streets, the bays
    for (a, b) in [((-380, py1 + 13.5), (380, py1 + 13.5)), ((px1 + 13.25, -380), (px1 + 13.25, 380))]:
        A, B = S(*a), S(*b)
        L = math.dist(A, B)
        u = ((B[0] - A[0]) / L, (B[1] - A[1]) / L)
        for k in range(int(L / 6)):
            c = (A[0] + u[0] * (k * 6 + 1.5), A[1] + u[1] * (k * 6 + 1.5))
            if plot.buffer(-0.5).contains(Point(c)):
                continue
            mb.box(c[0], c[1], 0.005, 3.0, 0.14, 0.01, 'Road line', rot=math.atan2(u[1], u[0]))
    # ---------------- the courtyard
    plaza = yard.buffer(-0.01)
    raised(mb, plaza, Z['paving'], 'Paving')
    # lawns: islands in the plaza (as on the model: green strips with trees)
    cx0, cy0 = px0 - 2, py0 - 18
    islands = []
    for (x0, y0, x1, y1) in [(cx0 + 4, cy0 + 4, cx0 + 22, cy0 + 9), (cx0 + 4, cy0 + 14, cx0 + 9, cy0 + 40),
                             (cx0 + 32, cy0 + 4, cx0 + 62, cy0 + 9)]:
        g = SB(x0, y0, x1, y1).intersection(yard.buffer(-1.5))
        if g.area > 5:
            islands.append(g)
    lawn = unary_union(islands) if islands else Polygon()
    raised(mb, lawn, Z['lawn'] + 0.12, 'Lawn')
    # the playground: rubber and equipment (ab/landscape.py), near the middle of the yard
    play = SB(cx0 + 14, cy0 + 14, cx0 + 34, cy0 + 28).intersection(yard.buffer(-2))
    if play.area > 30:
        raised(mb, play, Z['play'], 'Play orange')
        LS.playground(mb, play, Z['play'], rnd, people)
    # two pergolas (model photos): wood frame, slatted roof, benches
    for (x, y) in [(cx0 + 42, cy0 + 22), (cx0 + 52, cy0 + 30)]:
        pergola(mb, *S(x, y), Z['paving'], math.radians(-49.5))
        LS.WALK['solids'].append(affinity.rotate(box(S(x, y)[0] - 2.2, S(x, y)[1] - 1.6, S(x, y)[0] + 2.2, S(x, y)[1] + 1.6), -49.5, origin=S(x, y)))
    # a pool with fountains
    pool = SB(cx0 + 40, cy0 + 8, cx0 + 50, cy0 + 13).intersection(yard.buffer(-2))
    if pool.area > 10:
        mb.prism(pool.buffer(0.4), Z['paving'], Z['paving'] + 0.45, 'Stone white', 'Stone white')
        mb.polygon_face(pool, Z['paving'] + 0.35, 'Pool water')
        LS.WALK['solids'].append(pool.buffer(0.45))
    # trees: in the lawns, round planters in the plaza, along the streets
    for g in islands:
        for _ in range(int(g.area / 14)):
            p = rand_in(g, rnd)
            if p is not None:
                log_tree(mb, p.x, p.y, Z['lawn'], rnd.uniform(5.5, 9.0), rnd.uniform(2.0, 3.2), 'broad' if rnd.random() < 0.7 else 'conifer')
                trees.append((p.x, p.y))
    for k in range(10):
        p = rand_in(yard.buffer(-3).difference(lawn.buffer(2)).difference(play.buffer(3)).difference(pool.buffer(3)), rnd)
        if p is None:
            continue
        mb.prism(p.buffer(1.1, quad_segs=12), Z['paving'], Z['paving'] + 0.45, 'Stone white', 'Lawn')
        log_tree(mb, p.x, p.y, Z['paving'] + 0.45, rnd.uniform(5.0, 7.5), rnd.uniform(1.8, 2.6), 'broad')
        LS.WALK['solids'].append(p.buffer(1.15, quad_segs=8))
    # street trees: big planes along both streets, on both pavements (the videos: tall old trees)
    for line, step in [(((px0 - 60, py1 + 19.6), (px1 + 120, py1 + 19.6)), 9.0), (((px1 + 25.2, py0 - 120), (px1 + 25.2, py1 + 60)), 9.0),
                       (((px0 - 50, py1 + 3.6), (px1 - 4, py1 + 3.6)), 12.0), (((px1 + 3.6, py0 - 40), (px1 + 3.6, py1 - 4)), 12.0)]:
        (a, b) = line
        A, B = S(*a), S(*b)
        L = math.dist(A, B)
        for k in range(int(L / step)):
            t = (k + 0.5) * step / L
            x, y = A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t
            if any(Polygon(t_['outline']).buffer(3).contains(Point(x, y)) for t_ in towers) or podium_o.buffer(2.5).contains(Point(x, y)):
                continue
            log_tree(mb, x, y, Z['paving'], rnd.uniform(12, 17), rnd.uniform(3.5, 5.0), 'broad')
            trees.append((x, y))
    # trees in the city's yards and along its pavements
    for k in range(260):
        p = rand_in(lawn_city.intersection(Point(0, 0).buffer(420)), rnd)
        if p is None or p.distance(plot) < 8:
            continue
        log_tree(mb, p.x, p.y, Z['lawn'], rnd.uniform(8, 15), rnd.uniform(3, 5), 'broad' if rnd.random() < 0.85 else 'conifer')
    # ---------------- lamps
    for (a, b), step in [(((px0 - 40, py1 + 4.6), (px1 + 30, py1 + 4.6)), 24.0), (((px1 + 4.6, py0 - 60), (px1 + 4.6, py1 + 30)), 24.0)]:
        A, B = S(*a), S(*b)
        L = math.dist(A, B)
        u = ((B[0] - A[0]) / L, (B[1] - A[1]) / L)
        for k in range(int(L / step)):
            x, y = A[0] + u[0] * (k + 0.5) * step, A[1] + u[1] * (k + 0.5) * step
            nrm = math.atan2(-u[0], u[1])
            lamp(mb, x, y, Z['paving'], 8.0, street=True, rot=nrm)
    for k in range(9):
        p = rand_in(yard.buffer(-1.5).difference(lawn.buffer(1)).difference(play.buffer(1.5)), rnd)
        if p is not None:
            lamp(mb, p.x, p.y, Z['paving'], 4.0)
    # benches along the lawns
    for g in islands:
        ring = g.buffer(0.9).exterior
        for k in range(max(1, int(ring.length / 12))):
            p = ring.interpolate((k + 0.5) * ring.length / max(1, int(ring.length / 12)))
            q = ring.interpolate(min(ring.length, ring.project(p) + 0.5))
            rot = math.atan2(q.y - p.y, q.x - p.x)
            if play.buffer(2).contains(p):
                continue
            bench(mb, p.x, p.y, Z['paving'], rot)
            benches.append([round(p.x, 2), round(p.y, 2), round(rot, 3)])
    # ---------------- cars: in the bays (most of them), a few on the streets
    for g, ang in [(SB(*n_bay), 90), (SB(*e_bay), 0), (drive_bays, None)]:
        for q in parts(g):
            r = q.minimum_rotated_rectangle
            cs = list(r.exterior.coords)
            e1 = (cs[1][0] - cs[0][0], cs[1][1] - cs[0][1])
            e2 = (cs[2][0] - cs[1][0], cs[2][1] - cs[1][1])
            if math.hypot(*e1) < math.hypot(*e2):
                e1, e2 = e2, e1
            L = math.hypot(*e1)
            u = (e1[0] / L, e1[1] / L)
            c0 = (cs[0][0], cs[0][1])
            mid = r.centroid
            nb = int(L / 2.6)
            for k in range(nb):
                x = mid.x + u[0] * ((k + 0.5) * 2.6 - nb * 1.3)
                y = mid.y + u[1] * ((k + 0.5) * 2.6 - nb * 1.3)
                # the bay's white line
                v = (-u[1], u[0])
                lx, ly = x - u[0] * 1.3, y - u[1] * 1.3
                mb.box(lx, ly, 0.005, 0.1, 5.0, 0.01, 'Road line', rot=math.atan2(u[1], u[0]))
                if rnd.random() < 0.72:
                    rot = math.atan2(v[1], v[0]) + (math.pi if rnd.random() < 0.5 else 0)
                    cars.append([round(x, 2), round(y, 2), 0.0, round(rot, 3), rnd.randrange(6)])
    for (a, b) in [((-300, py1 + 11.6), (300, py1 + 11.6)), ((px1 + 10.2, -300), (px1 + 10.2, 300))]:
        A, B = S(*a), S(*b)
        L = math.dist(A, B)
        for k in range(10):
            t = rnd.uniform(0.1, 0.9)
            x, y = A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t
            if Point(x, y).distance(plot) < 6 and rnd.random() < 0.5:
                continue
            cars.append([round(x, 2), round(y, 2), 0.0, round(math.atan2(B[1] - A[1], B[0] - A[0]), 3), rnd.randrange(6)])
    # ---------------- people on the pavements and in the courtyard
    for k in range(70):
        g = pav if k < 40 else yard.difference(lawn).difference(pool.buffer(1) if pool.area else Polygon())
        p = rand_in(g.buffer(-0.6), rnd)
        if p is None:
            continue
        if any(Point(c[0], c[1]).distance(p) < 2.6 for c in cars):
            continue
        people.append([round(p.x, 2), round(p.y, 2), Z['paving'], rnd.randrange(6)])
    ob = make_object('Site', mb.to_mesh('Site', mats), col)
    walk = walk_map(towers, podium_o, plot, asphalt, unary_union([pav, plaza, city_pav]), lawn, play, houses, cars, people)
    return dict(trees=[], cars=cars, people=people, benches=benches, labels=labels, lamps=list(LS.LIGHTS), walk=walk,
                plot=plot, yard=yard)


def podium_bounds(O):
    """the podium's extent in the sheet frame"""
    a = math.radians(49.5)
    pts = [(math.cos(a) * x - math.sin(a) * y, math.sin(a) * x + math.cos(a) * y) for x, y in O.exterior.coords]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def rand_in(g, rnd, tries=60):
    g = g if g is not None else Polygon()
    if g.is_empty or g.area < 1:
        return None
    x0, y0, x1, y1 = g.bounds
    for _ in range(tries):
        p = Point(rnd.uniform(x0, x1), rnd.uniform(y0, y1))
        if g.contains(p):
            return p
    return None


def pergola(mb, x, y, z, rot):
    ca, sa = math.cos(rot), math.sin(rot)
    P = lambda u, v: (x + ca * u - sa * v, y + sa * u + ca * v)
    for u in (-2.0, 2.0):
        for v in (-1.4, 1.4):
            q = P(u, v)
            mb.box(q[0], q[1], z, 0.18, 0.18, 2.7, 'Wood', rot=rot)
    for u, v, w, d in ((0, -1.4, 4.4, 0.16), (0, 1.4, 4.4, 0.16)):
        q = P(u, v)
        mb.box(q[0], q[1], z + 2.7, w, d, 0.22, 'Wood', rot=rot)
    for k in range(11):
        q = P(-2.1 + k * 0.42, 0)
        mb.box(q[0], q[1], z + 2.92, 0.07, 3.2, 0.12, 'Lattice wood', rot=rot)
    for v in (-0.9, 0.9):
        q = P(0, v)
        mb.box(q[0], q[1], z + 0.42, 3.4, 0.42, 0.06, 'Wood', rot=rot)


def walk_map(towers, podium_o, plot, asphalt, paving, lawn, play, houses, cars, people):
    """the ground for walking on (src/sitewalk.js), as blender/ab/site.py walk_map (kinds: 1 asphalt,
    2 paving, 3 lawn, 4 play surface, 9 bare ground)"""
    W = LS.WALK
    R1 = lambda v: round(float(v), 2)
    ring = lambda g, tol=0.05: [[R1(x), R1(y)] for x, y in list(g.simplify(tol, preserve_topology=True).exterior.coords)[:-1]]
    solids = []

    def solid(g, tol=0.05):
        for q in parts(g):
            if q.area > 0.05:
                solids.append(ring(q, tol))
    solid(podium_o.buffer(0.35, join_style='mitre'), 0.1)
    area = plot.buffer(70)
    for h in houses:
        if h.intersects(area):
            solid(h.buffer(0.3, join_style='mitre'), 0.2)
    for g in W['solids']:
        solid(g)
    for c in cars:
        x, y, _, rot, _ = c
        if Point(x, y).distance(plot) < 80:
            solid(affinity.rotate(box(x - 2.35, y - 0.98, x + 2.35, y + 0.98), rot, origin=(x, y), use_radians=True))
    posts = [[R1(x), R1(y), R1(r)] for x, y, r in W['posts']]
    for t in LS_TREES():
        x, y, z, h, rr, kind = t
        if z < 1.0 and Point(x, y).distance(plot) < 80:
            posts.append([R1(x), R1(y), 0.3])
    for pe in people:
        posts.append([R1(pe[0]), R1(pe[1]), 0.28])
    lines = [[R1(w), [[R1(x), R1(y)] for x, y in c]] for w, c in W['lines']]
    x0, y0, x1, y1 = [math.floor(v) for v in area.bounds[:2]] + [math.ceil(v) for v in area.bounds[2:]]
    nx, ny = x1 - x0, y1 - y0
    X, Y = np.meshgrid(np.arange(nx) + x0 + 0.5, np.arange(ny) + y0 + 0.5)
    grid = np.zeros((ny, nx), np.uint8)

    def paint(kind, g):
        if g is None or g.is_empty:
            return
        shapely.prepare(g)
        grid[shapely.contains_xy(g, X, Y)] = kind
    paint(9, area)
    paint(1, asphalt)
    paint(2, paving)
    paint(3, lawn)
    paint(4, play)
    G, RW = 0.4, 0.3
    gx, gy = math.ceil(round(nx / G, 6)), math.ceil(round(ny / G, 6))
    CX, CY = np.meshgrid(x0 + (np.arange(gx) + 0.5) * G, y0 + (np.arange(gy) + 0.5) * G)
    ci, cj = np.floor(CX - x0).astype(int), np.floor(CY - y0).astype(int)
    on = (ci < nx) & (cj < ny)
    on[on] = grid[cj[on], ci[on]] != 0
    block = unary_union([Polygon(sr).buffer(RW - 0.02) for sr in solids]
                        + [LineString(c).buffer(RW + w / 2 - 0.02) for w, c in lines if len(c) > 1]
                        + [Point(x, y).buffer(RW + r - 0.02, quad_segs=8) for x, y, r in posts])
    shapely.prepare(block)
    roomy = on & ~shapely.contains_xy(block, CX, CY)
    reach = biggest_part(roomy)
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
    ri, rj = np.nonzero(reach.T)

    def snap(x, y):
        i, j = int((x - x0) / G), int((y - y0) / G)
        if 0 <= i < gx and 0 <= j < gy and reach[j, i]:
            return x, y
        k = np.argmin((ri - i) ** 2 + (rj - j) ** 2)
        return x0 + (ri[k] + 0.5) * G, y0 + (rj[k] + 0.5) * G
    # the start: in the courtyard, looking at the blocks; each block: 30-40 m off its courtyard face
    yard_c = plot.difference(podium_o).centroid
    sx, sy = snap(yard_c.x, yard_c.y)
    tc = unary_union([Polygon(t['outline']) for t in towers]).centroid
    spawn = dict(x=R1(sx), y=R1(sy), look=[R1(tc.x - sx), R1(tc.y - sy)], pitch=0.18)
    blocks = {}
    for t in towers:
        out = Polygon(t['outline'])
        c = out.centroid
        d = np.array([yard_c.x - c.x, yard_c.y - c.y])
        d = d / (np.hypot(*d) or 1)
        q = np.array([c.x, c.y]) + d * (math.sqrt(out.area) / 2 + 30)
        qx, qy = snap(*q)
        D = math.hypot(c.x - qx, c.y - qy)
        pitch = min(0.45, max(0.08, math.atan((t['top'] - 1.6) / max(D, 1)) - 0.55))
        blocks[t['key']] = dict(x=R1(qx), y=R1(qy), look=[R1(c.x - qx), R1(c.y - qy)], pitch=R1(pitch))
    return dict(x0=x0, y0=y0, nx=nx, ny=ny, step=1.0, ground=base64.b64encode(grid.tobytes()).decode(),
                solids=solids, lines=lines, posts=posts, spawn=spawn, blocks=blocks,
                reach=dict(step=G, gx=gx, gy=gy, runs=base64.b64encode(bytes(leb)).decode()),
                lawn=lawn_mask(lawn, dict(surf=[]), x0, y0, nx, ny))


def biggest_part(m):
    """the largest 4-connected part of a boolean grid"""
    from collections import deque
    lab = np.zeros(m.shape, np.int32)
    best, best_n, cur = 0, 0, 0
    H, W = m.shape
    for j0, i0 in zip(*np.nonzero(m)):
        if lab[j0, i0]:
            continue
        cur += 1
        lab[j0, i0] = cur
        q, n = deque([(j0, i0)]), 0
        while q:
            j, i = q.popleft()
            n += 1
            for jj, ii in ((j + 1, i), (j - 1, i), (j, i + 1), (j, i - 1)):
                if 0 <= jj < H and 0 <= ii < W and m[jj, ii] and not lab[jj, ii]:
                    lab[jj, ii] = cur
                    q.append((jj, ii))
        if n > best_n:
            best, best_n = cur, n
    return lab == best


def LS_TREES():
    from complex import geom
    return geom.TREE_LOG or []
