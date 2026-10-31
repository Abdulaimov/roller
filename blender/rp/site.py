"""Round the complex: the two streets it stands on as the developer's «Схема блокировки» draws them
(кӯчаи И. Нарзиқулова along Б and В, кӯчаи Ш. Ҳусейнзода along Б and А: their kerbs, the lay-bys
along the pavement, the drive down into the basement at В's west end), the courtyard inside the L of
the blocks as renders 5 and 8 show it (a drive along the blocks' yard faces past the doors, the yard
with its play zones, pergolas, fountains, planters and trees), the scheme's three houses (the
four-storey shopping centre of render 7 and two twelve-storey houses), and the neighbourhood from
OpenStreetMap (blender/rp/osm.json): the houses with their storeys, the roads; across кӯчаи
Ҳусейнзода the maternity hospital № 2, the school № 20 further on.

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

from .config import HERE, RAMP_X, sheet_to_site

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


# the developer's «Схема блокировки» (on every plan sheet), read off the vector drawing of sheet 17
# and fitted to the blocks (2.2442 m a point, Б's centre at the scheme's (115.835, 744.41) pt): the
# kerbs of the two streets at the corner, their lay-bys, the drive down into the basement at В's
# west end, the doors the arrows point at (sheet metres). (Its кӯчаи Шевченко is OSM's кӯчаи
# С.Абдуллоев to 10-15 m, the neighbourhood from OSM agrees with the scheme round the block.)
NARZ = (30.9, 38.7)                  # кӯчаи И. Нарзиқулова: its kerbs (sheet y)
HUSZ = (30.1, 41.9)                  # кӯчаи Ш. Ҳусейнзода: its kerbs (sheet x)
NARZ_BAY = [(-57.7, 24.7), (4.2, 24.7), (1.5, 30.9), (-60.4, 30.9)]
HUSZ_BAY = [(23.6, -47.5), (23.6, 14.2), (30.1, 16.4), (30.1, -45.0)]
RAMP = RAMP_X                        # the drive into the basement through В's west end (config)
DOORS = [(-50.2, -11.6), (-38.1, -11.6), (-16.0, -13.0), (-11.5, -19.0)]
# the courtyard drive (renders 5 and 8): along В's and А's yard faces past the doors, west to the
# lane behind В (OSM's service road at x -94) and out to кӯчаи Ҳусейнзода south of А; 6.5 m with a
# dashed centre line, a 4 m pavement at the doors (sheet boxes x0, y0, x1, y1)
DRIVE = [(-96.0, -22.1, -15.5, -15.6), (-22.0, -58.5, -15.5, -15.6), (-22.0, -58.5, HUSZ[0], -52.0)]
WALKS = [(-78.0, -15.6, -15.5, -11.6), (-15.5, -52.0, -11.4, -15.6), (-15.5, -52.0, 19.3, -47.8)]

def build_site(mats, col, towers, podium_o):
    rnd = random.Random(11)
    LS.walk_reset()
    mb = MeshBuilder()
    trees, cars, people, benches, labels = [], [], [], [], []
    notes = []   # what could not be placed as the renders have it (printed, README)
    osm = json.load(open(os.path.join(HERE, 'osm.json')))
    # the three houses inside the block where the scheme puts them: the four-storey shopping centre
    # of render 7 and two twelve-storey houses
    schema = json.load(open(os.path.join(HERE, 'schema_neighbours.json')))
    schema_g = [Polygon(q['ring']).buffer(0) for q in schema]
    schema_all = unary_union(schema_g)

    # ---------------- the streets (the scheme): the carriageways, the lay-bys, the pavements
    px0, py0, px1, py1 = podium_bounds(podium_o)
    n_road = SB(-420, NARZ[0], 420, NARZ[1])
    e_road = SB(HUSZ[0], -420, HUSZ[1], 420)
    roads = unary_union([n_road, e_road])
    bays = unary_union([SP(NARZ_BAY), SP(HUSZ_BAY)])
    # the drive down into the basement: across the pavement to the ramp's door in the podium
    ramp_drive = SB(RAMP[0], py1 - 0.5, RAMP[1], NARZ[0])
    n_pav = SB(px0 - 60, py1, px1 + 60, NARZ[0]).difference(bays).difference(ramp_drive)
    e_pav = SB(px1, py0 - 60, HUSZ[0], NARZ[0]).difference(bays)
    n_far = SB(px0 - 60, NARZ[1], px1 + 60, NARZ[1] + 5.0)
    e_far = SB(HUSZ[1], py0 - 60, HUSZ[1] + 5.0, py1 + 60)
    # the plot: the podium, the courtyard and its drive, between the scheme's houses and the streets
    drive = unary_union([SB(*b) for b in DRIVE])
    walks = unary_union([SB(*b) for b in WALKS]).difference(podium_o)
    plot = unary_union([SB(-96.0, -64.0, px1, py1), SB(-22.0, -58.5, HUSZ[0], -47.8)])
    yard = SB(-76.0, -64.0, -22.0, -22.1).difference(schema_all.buffer(4.0, join_style='mitre')).difference(podium_o.buffer(0.5))
    yard = max(parts(yard), key=lambda q: q.area)
    # the rest of the plot round the scheme's houses: paved
    pav = unary_union([n_pav, e_pav, walks, n_far, e_far]).difference(roads.union(bays)).difference(podium_o)
    # the rest of the plot (behind В's west end, between the yard and the scheme's houses): lawns with
    # trees inside a paved rim 2 m wide, not one paved field (renders 5 and 8 have no bare plaza)
    rest = plot.difference(podium_o).difference(drive).difference(yard).difference(schema_all.buffer(0.3)).difference(roads).difference(pav)
    green = unary_union([q.buffer(-2.0, join_style='mitre') for q in parts(rest) if q.area > 40])
    green = unary_union([q for q in parts(green) if q.area > 12]) if not green.is_empty else Polygon()
    pav = pav.union(rest.difference(green))

    # ---------------- the neighbourhood's roads (OSM), with pavements; none in the block
    city_roads = []
    for r in osm['roads']:
        ln = LineString(r['line'])
        city_roads.append(ln.buffer(r['w'] / 2, cap_style='flat'))
    city_roads = unary_union(city_roads) if city_roads else Polygon()
    region = Point(0, 0).buffer(560)
    city_roads = city_roads.intersection(region).difference(plot.buffer(1))
    city_pav = city_roads.buffer(2.6).difference(city_roads).difference(plot.buffer(1)).intersection(region)
    asphalt = unary_union([roads, bays, drive, ramp_drive, city_roads]).intersection(region)

    # ---------------- the neighbours' houses
    houses = []
    tones = ['Neighbour cream', 'Neighbour solid', 'Neighbour peach', 'Neighbour solid', 'Neighbour cream', 'Neighbour blue', 'Neighbour rose']
    hb = MeshBuilder()
    streets_all = unary_union([roads, bays, n_pav, e_pav])
    for i, bld in enumerate(osm['buildings']):
        g = Polygon(bld['ring']).buffer(0)
        if g.is_empty or not region.contains(g.centroid):
            continue
        g = g.simplify(0.3)
        # (none on the plot or the scheme's houses and streets)
        if g.intersects(plot.buffer(2)) or g.intersects(schema_all.buffer(3)) or g.intersection(streets_all).area > 1.0:
            continue
        if g.intersects(city_roads):
            g = g.difference(city_roads.buffer(3.5))
            g = max(parts(g), key=lambda q: q.area) if parts(g) else Polygon()
            if g.area < 60:
                continue
        lv = bld['levels'] or (4 if g.area > 150 else 2)
        # (renders 1 and 4: the houses across the two streets stand about nine storeys, not the
        # nineteen OSM gives them - they hid block В)
        if g.distance(podium_o) < 50 and lv > 9:
            lv = 9
        if 'Роддом' in str(bld.get('name')) or bld.get('amenity') == 'hospital':
            mat = 'Neighbour cream'
        else:
            mat = tones[i % len(tones)]
        h = 3.1 * lv + 0.6
        hb.prism(g, -0.3, h, mat, 'Roof')
        if g.area > 80:
            hb.prism(g.exterior.buffer(0.15).intersection(g), h, h + 0.7, mat, 'Roof')
        houses.append(g)
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
    for q, g in zip(schema, schema_g):
        if q['fill'][0] < 0.3:
            trade_centre(mb, g)
        else:
            h = 3.1 * 12 + 0.6
            hb.prism(g, -0.3, h, 'Neighbour solid', 'Roof')
            hb.prism(g.exterior.buffer(0.15).intersection(g), h, h + 0.7, 'Neighbour solid', 'Roof')
        houses.append(g)
    make_object('Neighbours', hb.to_mesh('Neighbours', mats), col)

    # ---------------- ground
    base = region.difference(asphalt)
    mb.polygon_face(region.buffer(400).difference(region), -0.05, 'Ground')
    lawn_city = base.difference(city_pav).difference(pav).difference(plot).difference(unary_union(houses).buffer(0.5) if houses else Polygon())
    # (renders 4 and 5: round the block the city is grey - paved squares and yards with trees in
    # them, the houses white; the lawns further out stay)
    city_sq = lawn_city.intersection(Point(0, 0).buffer(150))
    raised(mb, lawn_city.difference(city_sq), Z['lawn'] - 0.05, 'Lawn')
    raised(mb, city_sq, Z['paving'] - 0.04, 'City paving')
    raised(mb, city_pav.difference(asphalt).difference(pav), Z['paving'], 'Sidewalk')
    raised(mb, pav.difference(yard), Z['paving'], 'Paving')
    raised(mb, green, Z['lawn'], 'Lawn')
    for q in parts(green):
        for k in range(max(1, int(q.area / 70))):
            p = rand_in(q.buffer(-1.5), rnd)
            if p is not None:
                log_tree(mb, p.x, p.y, Z['lawn'], rnd.uniform(6.0, 9.0), rnd.uniform(2.0, 3.0), 'broad')
                trees.append((p.x, p.y))
                LS.WALK['posts'].append([p.x, p.y, 0.35])
    mb.polygon_face(asphalt, 0.0, 'Asphalt')
    # road markings: the centre lines of the streets and of the courtyard's drive (dashed)
    for (a, b) in [((-380, sum(NARZ) / 2), (380, sum(NARZ) / 2)), ((sum(HUSZ) / 2, -380), (sum(HUSZ) / 2, 380)),
                   ((-94.0, -18.85), (-18.75, -18.85)), ((-18.75, -18.85), (-18.75, -55.25)), ((-18.75, -55.25), (HUSZ[0] - 1, -55.25))]:
        A, B = S(*a), S(*b)
        L = math.dist(A, B)
        if L < 1:
            continue
        u = ((B[0] - A[0]) / L, (B[1] - A[1]) / L)
        for k in range(int(L / 6)):
            c = (A[0] + u[0] * (k * 6 + 1.5), A[1] + u[1] * (k * 6 + 1.5))
            if not asphalt.contains(Point(c)):
                continue
            mb.box(c[0], c[1], 0.005, 3.0, 0.14, 0.01, 'Road line', rot=math.atan2(u[1], u[0]))

    # the zebra crossings at the corner, over both streets (renders 1, 4)
    crn = random.Random('corner')   # (its own: the courtyard keeps its draws)
    rot_x = math.radians(-49.5)   # the sheet's x on the ground
    for k in range(8):
        c = S(25.75, NARZ[0] + 0.5 + k * (NARZ[1] - NARZ[0] - 1.0) / 7)
        mb.box(c[0], c[1], 0.005, 3.5, 0.5, 0.012, 'Road line', rot=rot_x)
    for k in range(12):
        c = S(HUSZ[0] + 0.5 + k * (HUSZ[1] - HUSZ[0] - 1.0) / 11, 25.75)
        mb.box(c[0], c[1], 0.005, 0.5, 3.5, 0.012, 'Road line', rot=rot_x)
    # the corner's bed along кӯчаи Нарзиқулова (render 4): dark gravel, a lawn curving through it, a
    # clipped ball, two clipped hedges, cypresses round it and by the crossing
    bed = SB(8.0, 25.2, 25.0, 30.3)
    mb.prism(bed, 0.0, Z['paving'] + 0.06, 'Kerb', 'Mulch')
    wave = [(8.0 + 17.0 * i / 24, 27.6 + 1.5 * math.sin(math.pi * 2 * i / 24)) for i in range(25)]
    curve = SP([(x, y + 0.9) for x, y in wave] + [(x, y - 0.9) for x, y in reversed(wave)]).intersection(bed.buffer(-0.3))
    raised(mb, curve, Z['paving'] + 0.1, 'Lawn')
    c = S(12.0, 27.4)
    mb.blob(c[0], c[1], Z['paving'] + 0.55, 0.9, 0.9, 0.55, 'Shrub', subdiv=2, jitter=0.03, rnd=crn)
    for hx0, hy0, hx1, hy1 in ((18.5, 25.6, 24.4, 26.3), (19.5, 28.6, 24.4, 29.3)):
        mb.prism(SB(hx0, hy0, hx1, hy1), Z['paving'], Z['paving'] + 0.75, 'Shrub', 'Shrub')
    for x, y in ((10.0, 29.6), (14.5, 25.9), (27.2, 28.6), (27.2, 17.6), (27.2, 19.8), (21.2, 21.0)):
        c = S(x, y)
        log_tree(mb, c[0], c[1], Z['paving'], crn.uniform(4.8, 5.6), 0.7, 'conifer')
        trees.append(c)
        LS.WALK['posts'].append([c[0], c[1], 0.45])
    LS.WALK['solids'].append(bed)

    # ---------------- the courtyard (renders 5 and 8; no landscaping plan in the book, the pieces
    # where render 8 shows them, read off the render by eye - the camera looks east along В's yard face):
    # beige and grey pavers, three blue rubber play zones with their equipment, two pergolas over
    # timber decks, two square fountains, the white box at the drive (the basement's stair), a round
    # planter ringed by a timber bench, round lawns with a tree, trees in white pots, cypresses along
    # the drive, low planters with shrubs along the south edge
    raised(mb, yard.buffer(-0.01), Z['paving'], 'Paving')
    taken = []
    R = lambda x, y, w, d: SP([(x - w / 2, y - d / 2), (x + w / 2, y - d / 2), (x + w / 2, y + d / 2), (x - w / 2, y + d / 2)])

    def put(name, x, y, w, d, gap=1.0):
        """the piece where the render has it, or the nearest place within 4 m it fits (inside the
        yard, clear of the pieces placed before it)"""
        inner = yard.buffer(-0.6)
        occ = unary_union(taken) if taken else Polygon()
        for r in range(0, 9):
            for ex, ey in [(0, 0)] if r == 0 else [(r * 0.5, 0), (-r * 0.5, 0), (0, r * 0.5), (0, -r * 0.5), (r * 0.35, r * 0.35), (-r * 0.35, r * 0.35), (r * 0.35, -r * 0.35), (-r * 0.35, -r * 0.35)]:
                foot = R(x + ex, y + ey, w, d)
                if inner.contains(foot) and not foot.buffer(gap).intersects(occ):
                    if r:
                        notes.append(f'{name}: moved {math.hypot(ex, ey):.1f} m from where render 8 has it')
                    taken.append(foot)
                    return x + ex, y + ey, foot
        notes.append(f'{name}: no room, left out')
        return None
    plays = []

    def play_zone(name, x, y, w, d):
        got = put(name, x, y, w, d)
        if got:
            q = got[2].buffer(-1.2).buffer(1.2)
            plays.append(q)
            raised(mb, q, Z['play'], 'Play orange')
            LS.playground(mb, q, Z['play'], rnd, people)
    play_zone('the big play zone', -57.0, -35.0, 13.0, 8.5)
    play_zone('the play zone at the pergolas', -41.0, -47.0, 10.0, 6.5)
    play_zone('the play strip along the drive', -54.5, -25.6, 9.0, 4.4)
    play = unary_union(plays) if plays else Polygon()
    for name, (x, y) in (('the pergola by the inner corner', (-33.0, -28.5)), ('the pergola in the middle', (-46.5, -35.0))):
        got = put(name, x, y, 7.4, 4.6, 1.2)
        if got:
            c = S(got[0], got[1])
            pergola(mb, c[0], c[1], Z['paving'], math.radians(-49.5))
            LS.WALK['solids'].append(got[2].buffer(-0.3))
    pools = []
    for name, (x, y) in (('the fountain by the drive', (-45.0, -26.2)), ('the fountain in the south', (-56.0, -44.5))):
        got = put(name, x, y, 4.0, 4.0, 1.5)
        if not got:
            continue
        c = S(got[0], got[1])
        q = R(got[0], got[1], 3.2, 3.2)
        mb.prism(q.buffer(0.35, join_style='mitre').difference(q), Z['paving'], Z['paving'] + 0.5, 'Stone dark', 'Stone dark')
        mb.polygon_face(q, Z['paving'] + 0.35, 'Pool water')
        for k in (-1, 0, 1):
            mb.box(c[0] + k * 0.75, c[1] + k * 0.2, Z['paving'] + 0.35, 0.06, 0.06, 1.1 - 0.3 * abs(k), 'Pool water')
        pools.append(q)
        LS.WALK['solids'].append(q.buffer(0.4))
    pool = unary_union(pools) if pools else Polygon()
    got = put('the white box (the basement stair)', -28.5, -41.0, 4.6, 4.6, 1.5)
    if got:
        mb.prism(got[2], Z['paving'], Z['paving'] + 3.6, 'Pilaster white', 'Pilaster white')
        LS.WALK['solids'].append(got[2])
    got = put('the round planter with its bench', -66.0, -43.0, 5.6, 5.6, 1.5)
    if got:
        p = Point(S(got[0], got[1]))
        mb.prism(p.buffer(2.6, quad_segs=24).difference(p.buffer(2.1, quad_segs=24)), Z['paving'], Z['paving'] + 0.45, 'Stone white', 'Wood')
        mb.prism(p.buffer(2.1, quad_segs=24), Z['paving'], Z['paving'] + 0.55, 'Stone white', 'Lawn')
        log_tree(mb, p.x, p.y, Z['paving'] + 0.55, 7.5, 2.8, 'broad')
        trees.append((p.x, p.y))
        LS.WALK['solids'].append(p.buffer(2.65))
    islands = []
    for name, (x, y) in (('the round lawn in the west', (-69.0, -33.0)), ('the round lawn in the middle', (-47.0, -41.5))):
        got = put(name, x, y, 4.4, 4.4, 1.2)
        if not got:
            continue
        p = Point(S(got[0], got[1]))
        mb.prism(p.buffer(2.1, quad_segs=24).difference(p.buffer(1.9, quad_segs=24)), Z['paving'], Z['paving'] + 0.22, 'Stone white', 'Stone white')
        islands.append(p.buffer(1.9, quad_segs=24))
        log_tree(mb, p.x, p.y, Z['lawn'], rnd.uniform(5.5, 7.0), rnd.uniform(2.0, 2.6), 'broad')
        trees.append((p.x, p.y))
    lawn = unary_union(islands) if islands else Polygon()
    raised(mb, lawn, Z['lawn'] + 0.05, 'Lawn')
    for k, (x, y) in enumerate([(-62.0, -27.0), (-38.5, -33.0), (-27.0, -34.0), (-51.0, -40.5), (-63.0, -37.5), (-35.0, -52.0), (-30.0, -48.5), (-71.0, -40.0)]):
        got = put(f'a tree in a pot ({k + 1})', x, y, 1.4, 1.4, 1.0)
        if not got:
            continue
        c = S(got[0], got[1])
        mb.prism(Point(c).buffer(0.62, quad_segs=16), Z['paving'], Z['paving'] + 0.55, 'Stone white', 'Mulch')
        log_tree(mb, c[0], c[1], Z['paving'] + 0.55, rnd.uniform(4.0, 5.2), rnd.uniform(1.3, 1.8), 'broad')
        trees.append(c)
        LS.WALK['solids'].append(Point(c).buffer(0.68))
    # cypresses in a planting strip along the drive (render 8: by the fountain and the play strip)
    strip = SB(-72.0, -24.0, -30.0, -22.6).difference(unary_union(taken).buffer(0.8) if taken else Polygon())
    for q in parts(strip):
        if q.area < 2:
            continue
        mb.prism(q, Z['paving'], Z['paving'] + 0.35, 'Stone white', 'Mulch')
        LS.WALK['solids'].append(q)
        ln = LineString([S(-72.0, -23.3), S(-30.0, -23.3)])
        for k in range(int(ln.length / 3.2)):
            p = ln.interpolate((k + 0.5) * 3.2)
            if q.buffer(-0.3).contains(p):
                log_tree(mb, p.x, p.y, Z['paving'] + 0.35, rnd.uniform(5.8, 7.0), 0.65, 'conifer')
                trees.append((p.x, p.y))
    # planting beds by the pergolas and the play zones, and more trees in pots where there is room
    # (render 8 has about thirty trees in the yard and green beds round the play areas)
    for k, (x, y, w, d) in enumerate([(-38.5, -28.4, 4.0, 1.6), (-52.0, -35.0, 1.6, 4.0), (-46.5, -30.5, 4.0, 1.4), (-34.5, -45.5, 1.6, 4.0),
                                     (-62.5, -31.0, 1.6, 4.0), (-50.0, -45.5, 4.0, 1.6), (-28.0, -46.5, 1.6, 4.0), (-70.0, -46.5, 4.0, 1.6)]):
        got = put(f'a planting bed ({k + 1})', x, y, w, d, 0.8)
        if not got:
            continue
        mb.prism(got[2], Z['paving'], Z['paving'] + 0.4, 'Stone white', 'Mulch')
        mb.prism(got[2].buffer(-0.15), Z['paving'] + 0.4, Z['paving'] + 0.85, 'Shrub', 'Shrub')
        c = S(got[0], got[1])
        log_tree(mb, c[0], c[1], Z['paving'] + 0.4, rnd.uniform(4.2, 5.5), rnd.uniform(1.4, 1.9), 'broad')
        trees.append(c)
        LS.WALK['solids'].append(got[2])
    extra = 0
    for (x, y) in [(xx, yy) for yy in np.arange(-25.5, -60.0, -3.4) for xx in np.arange(-73.5, -24.0, 3.4)]:
        if extra >= 14:
            break
        if rnd.random() < 0.45:
            continue
        foot = R(x, y, 1.4, 1.4)
        occ = unary_union(taken) if taken else Polygon()
        if not yard.buffer(-0.8).contains(foot) or foot.buffer(1.6).intersects(occ):
            continue
        taken.append(foot)
        c = S(x, y)
        mb.prism(Point(c).buffer(0.62, quad_segs=16), Z['paving'], Z['paving'] + 0.55, 'Stone white', 'Mulch')
        log_tree(mb, c[0], c[1], Z['paving'] + 0.55, rnd.uniform(4.0, 5.2), rnd.uniform(1.3, 1.8), 'broad')
        trees.append(c)
        LS.WALK['solids'].append(Point(c).buffer(0.68))
        extra += 1
    notes.append(f'{extra} more trees in pots where the yard had room')
    # low planters with shrubs along the yard's south edge (render 8, right)
    for k, (x, y) in enumerate([(-36.0, -57.5), (-32.0, -57.5), (-28.0, -57.5), (-24.5, -57.5)]):
        got = put(f'a shrub planter ({k + 1})', x, y, 3.0, 1.2, 0.6)
        if got:
            mb.prism(got[2], Z['paving'], Z['paving'] + 0.45, 'Stone white', 'Mulch')
            mb.prism(got[2].buffer(-0.12), Z['paving'] + 0.45, Z['paving'] + 1.0, 'Shrub', 'Shrub')
            LS.WALK['solids'].append(got[2])

    # the yard's edge to the shopping centre's square: a white retaining wall with a dark slatted
    # fence on it (renders 5 and 8, right)
    tc = [g for q, g in zip(schema, schema_g) if q['fill'][0] < 0.3]
    if tc:
        edge = yard.exterior.intersection(tc[0].buffer(4.6, join_style='mitre'))
        for ln in getattr(edge, 'geoms', [edge]):
            if ln.geom_type != 'LineString' or ln.length < 2.0:
                continue
            pts = list(ln.coords)
            n = len(pts)
            mb.tube(pts, [0.0] * n, [Z['paving'] + 0.9] * n, 0.3, 'Pilaster white')
            mb.ribbon(pts, Z['paving'] + 0.9, Z['paving'] + 2.1, 'Screen dark', double=True)
            mb.tube(pts, [Z['paving'] + 2.1] * n, [Z['paving'] + 2.16] * n, 0.08, 'Frame dark')
            for k in range(int(ln.length / 2.5) + 1):
                q = ln.interpolate(min(ln.length, k * 2.5))
                mb.box(q.x, q.y, Z['paving'] + 0.9, 0.08, 0.08, 1.26, 'Frame dark')
            LS.WALK['solids'].append(ln.buffer(0.25))

    # ---------------- street trees: on the far pavements trees of the street; on the podium's own
    # pavements narrow cypresses and a low clipped hedge (renders 1, 4, 6)
    for (a, b), step, near in [(((px0 - 60, NARZ[1] + 2.5), (px1 + 120, NARZ[1] + 2.5)), 8.0, False),
                               (((HUSZ[1] + 2.5, py0 - 120), (HUSZ[1] + 2.5, py1 + 60)), 8.0, False),
                               (((NARZ_BAY[3][0] - 2, 23.4), (NARZ_BAY[2][0] + 2, 23.4)), 12.0, True),
                               (((22.4, HUSZ_BAY[0][1] - 2), (22.4, HUSZ_BAY[1][1] + 2)), 12.0, True)]:
        A, B = S(*a), S(*b)
        L = math.dist(A, B)
        for k in range(int(L / step)):
            t = (k + 0.5) * step / L
            x, y = A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t
            P_ = Point(x, y)
            if any(Polygon(t_['outline']).buffer(3).contains(P_) for t_ in towers) or podium_o.buffer(2.5).contains(P_) or asphalt.buffer(1.0).contains(P_) \
                    or unary_union(houses).buffer(2.0).contains(P_):
                continue
            if near:
                log_tree(mb, x, y, Z['paving'], rnd.uniform(5.0, 6.5), rnd.uniform(0.6, 0.8), 'conifer')
            else:
                log_tree(mb, x, y, Z['paving'], rnd.uniform(8, 11), rnd.uniform(2.6, 3.6), 'broad')
            trees.append((x, y))
        if not near:
            # (the far kerbs: the trees stand in a clipped hedge, render 4)
            off = (-(B[1] - A[1]) / L, (B[0] - A[0]) / L)
            side = -1.4 if a[1] == b[1] else 1.4
            ln = LineString([(A[0] + off[0] * side, A[1] + off[1] * side), (B[0] + off[0] * side, B[1] + off[1] * side)])
            hedge = ln.buffer(0.45, cap_style=2).difference(asphalt.buffer(0.3)).difference(unary_union(houses).buffer(1.0))
            for q in parts(hedge):
                if q.area > 0.5:
                    mb.prism(q, Z['paving'], Z['paving'] + 0.65, 'Shrub', 'Shrub')
                    LS.WALK['solids'].append(q.buffer(0.1))
        if near:
            hedge = LineString([A, B]).buffer(0.3, cap_style=2).difference(podium_o.buffer(1.0)).difference(asphalt.buffer(0.6))
            for t_ in towers:
                hedge = hedge.difference(Polygon(t_['outline']).buffer(3))
            for q in getattr(hedge, 'geoms', [hedge]):
                if q.geom_type == 'Polygon' and q.area > 0.5:
                    mb.prism(q, Z['paving'], Z['paving'] + 0.8, 'Shrub', 'Shrub')
                    LS.WALK['solids'].append(q.buffer(0.1))
    # trees in the city's yards and along its pavements (OSM's lawns, none on the roads)
    for k in range(260):
        p = rand_in(lawn_city.intersection(Point(0, 0).buffer(420)), rnd)   # (city_sq is part of it)
        if p is None or p.distance(plot) < 8 or asphalt.buffer(1.5).contains(p):
            continue
        log_tree(mb, p.x, p.y, Z['lawn'], rnd.uniform(8, 15), rnd.uniform(3, 5), 'broad' if rnd.random() < 0.85 else 'conifer')
    # ---------------- lamps: along the podium's pavements and in the courtyard
    for (a, b), step in [(((px0 - 40, NARZ[0] - 0.6), (px1 + 30, NARZ[0] - 0.6)), 24.0), (((HUSZ[0] - 0.6, py0 - 60), (HUSZ[0] - 0.6, py1 + 30)), 24.0)]:
        A, B = S(*a), S(*b)
        L = math.dist(A, B)
        u = ((B[0] - A[0]) / L, (B[1] - A[1]) / L)
        for k in range(int(L / step)):
            x, y = A[0] + u[0] * (k + 0.5) * step, A[1] + u[1] * (k + 0.5) * step
            if asphalt.contains(Point(x, y)) or podium_o.buffer(0.5).contains(Point(x, y)):
                continue
            nrm = math.atan2(-u[0], u[1])
            lamp(mb, x, y, Z['paving'], 8.0, street=True, rot=nrm)
    for k in range(10):
        p = rand_in(yard.buffer(-1.5).difference(unary_union(taken).buffer(1.2) if taken else Polygon()), rnd)
        if p is not None:
            lamp(mb, p.x, p.y, Z['paving'], 4.0)
    # benches round the lawns
    for g in islands:
        ring = g.buffer(0.9).exterior
        for k in range(max(1, int(ring.length / 12))):
            p = ring.interpolate((k + 0.5) * ring.length / max(1, int(ring.length / 12)))
            q = ring.interpolate(min(ring.length, ring.project(p) + 0.5))
            rot = math.atan2(q.y - p.y, q.x - p.x)
            if play.buffer(2).contains(p) or any(t_.contains(p) for t_ in taken):
                continue
            bench(mb, p.x, p.y, Z['paving'], rot)
            benches.append([round(p.x, 2), round(p.y, 2), round(rot, 3)])
    # ---------------- cars: in the lay-bys (across them), a few on the streets
    for g in (SP(NARZ_BAY), SP(HUSZ_BAY)):
        r = g.minimum_rotated_rectangle
        cs = list(r.exterior.coords)
        e1 = (cs[1][0] - cs[0][0], cs[1][1] - cs[0][1])
        e2 = (cs[2][0] - cs[1][0], cs[2][1] - cs[1][1])
        if math.hypot(*e1) < math.hypot(*e2):
            e1, e2 = e2, e1
        L = math.hypot(*e1)
        u = (e1[0] / L, e1[1] / L)
        mid = r.centroid
        nb = int(L / 2.6)
        for k in range(nb):
            x = mid.x + u[0] * ((k + 0.5) * 2.6 - nb * 1.3)
            y = mid.y + u[1] * ((k + 0.5) * 2.6 - nb * 1.3)
            if not g.buffer(0.2).contains(Point(x, y)):
                continue
            v = (-u[1], u[0])
            lx, ly = x - u[0] * 1.3, y - u[1] * 1.3
            mb.box(lx, ly, 0.005, 0.1, 5.0, 0.01, 'Road line', rot=math.atan2(u[1], u[0]))
            if rnd.random() < 0.72:
                rot = math.atan2(v[1], v[0]) + (math.pi if rnd.random() < 0.5 else 0)
                cars.append([round(x, 2), round(y, 2), 0.0, round(rot, 3), rnd.randrange(6)])
    for (a, b) in [((-300, NARZ[0] + 2.0), (300, NARZ[0] + 2.0)), ((HUSZ[0] + 2.0, -300), (HUSZ[0] + 2.0, 300))]:
        A, B = S(*a), S(*b)
        for k in range(10):
            t = rnd.uniform(0.1, 0.9)
            x, y = A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t
            if Point(x, y).distance(plot) < 6 and rnd.random() < 0.5:
                continue
            cars.append([round(x, 2), round(y, 2), 0.0, round(math.atan2(B[1] - A[1], B[0] - A[0]), 3), rnd.randrange(6)])
    # ---------------- people on the pavements and in the courtyard
    for k in range(70):
        g = pav if k < 40 else yard.difference(lawn).difference(pool.buffer(1) if pool.area else Polygon()).difference(unary_union(taken) if taken else Polygon())
        p = rand_in(g.buffer(-0.6), rnd)
        if p is None:
            continue
        if any(Point(c[0], c[1]).distance(p) < 2.6 for c in cars):
            continue
        people.append([round(p.x, 2), round(p.y, 2), Z['paving'], rnd.randrange(6)])
    for n in notes:
        print('courtyard:', n)
    ob = make_object('Site', mb.to_mesh('Site', mats), col)
    walk = walk_map(towers, podium_o, plot, asphalt, unary_union([pav, yard, city_pav]), lawn, play, houses, cars, people)
    return dict(trees=[], cars=cars, people=people, benches=benches, labels=labels, lamps=list(LS.LIGHTS), walk=walk,
                plot=plot, yard=yard, notes=notes)


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
    """render 8's pergola: a timber deck, dark posts and beams, a roof of pale slats, slatted dark
    screens at its ends, two benches under it"""
    ca, sa = math.cos(rot), math.sin(rot)
    P = lambda u, v: (x + ca * u - sa * v, y + sa * u + ca * v)
    mb.box(x, y, z, 7.0, 4.2, 0.18, 'Wood', rot=rot)
    for u in (-3.2, 3.2):
        for v in (-1.8, 1.8):
            q = P(u, v)
            mb.box(q[0], q[1], z + 0.18, 0.16, 0.16, 2.8, 'Frame dark', rot=rot)
    for v in (-1.8, 1.8):
        q = P(0, v)
        mb.box(q[0], q[1], z + 2.98, 6.8, 0.16, 0.25, 'Frame dark', rot=rot)
    for k in range(23):
        q = P(-3.3 + k * 0.3, 0)
        mb.box(q[0], q[1], z + 3.23, 0.08, 4.0, 0.12, 'Pilaster white', rot=rot)
    for u in (-3.2, 3.2):
        for k in range(9):
            q = P(u, -1.6 + k * 0.4)
            mb.box(q[0], q[1], z + 0.18, 0.1, 0.06, 2.8, 'Frame dark', rot=rot)
    for v in (-1.0, 1.0):
        q = P(0, v)
        mb.box(q[0], q[1], z + 0.45, 4.0, 0.45, 0.06, 'Wood', rot=rot)


def trade_centre(mb, g):
    """the scheme's four-storey shopping and services centre (render 7): glazed storeys in a dark
    grid between projecting white slab bands, timber fins over a third of each long face, the top
    floor's terrace under a white canopy on posts (the glass was the shops' see-through glass, the
    building read as an empty frame - 29.10.2026)"""
    FH = 4.2
    inner = g.buffer(-0.3, join_style='mitre')
    for k in range(4):
        z = k * FH
        mb.prism(inner, z, z + FH - 0.45, 'Glass light', 'Shop floor')
        band = g.buffer(0.25, join_style='mitre').difference(inner)
        mb.prism(band, z + FH - 0.45, z + FH, 'White band', 'White band', 'White band')
        # the curtain wall's grid: mullions about every 1.6 m, a transom 1.1 m up
        pts = list(inner.exterior.coords)
        for a_, b_ in zip(pts, pts[1:]):
            L = math.dist(a_, b_)
            if L < 0.5:
                continue
            u = ((b_[0] - a_[0]) / L, (b_[1] - a_[1]) / L)
            rot = math.atan2(u[1], u[0])
            n = max(1, round(L / 1.6))
            for j in range(n + 1):
                t = min(L - 0.04, max(0.04, j * L / n))
                mb.box(a_[0] + u[0] * t, a_[1] + u[1] * t, z, 0.07, 0.12, FH - 0.45, 'Frame dark', rot=rot)
            for zz in (z + 1.1,):
                mb.box((a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2, zz, L, 0.12, 0.06, 'Frame dark', rot=rot)
    top = 4 * FH
    mb.prism(g, top, top + 0.2, 'White band', 'Roof')
    pts = list(g.exterior.coords)
    c = g.centroid
    for a, b in sorted(zip(pts, pts[1:]), key=lambda e: -math.dist(*e))[:2]:
        L = math.dist(a, b)
        u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        n = (u[1], -u[0])
        if (c.x - (a[0] + b[0]) / 2) * n[0] + (c.y - (a[1] + b[1]) / 2) * n[1] > 0:
            n = (-n[0], -n[1])
        # (render 7: the fins over the right third of the face, the glass bare elsewhere)
        for k in range(int(L / 3 / 0.45)):
            t = L * 2 / 3 + 0.22 + k * 0.45
            mb.box(a[0] + u[0] * t + n[0] * 0.32, a[1] + u[1] * t + n[1] * 0.32, 0.0, 0.08, 0.28, top, 'Wood', rot=math.atan2(u[1], u[0]))
    canopy = g.buffer(-1.0, join_style='mitre')
    mb.prism(canopy, top + 3.2, top + 3.5, 'White band', 'White band', 'White band')
    for p in list(canopy.exterior.coords)[:-1]:
        mb.box(p[0], p[1], top + 0.2, 0.3, 0.3, 3.0, 'Stone white')
    mb.prism(g.difference(g.buffer(-0.06, join_style='mitre')), top + 0.2, top + 1.1, 'Railing glass', 'Frame dark', 'Railing glass')


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
