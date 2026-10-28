"""Floor plans of the Ali Binokor blocks (vector PDFs) -> walls, columns, windows, rooms, apartments.

    tools/ab/py tools/ab/extract_plan.py [KEY ...]   # -> blender/ab/plans.json, build/plans/KEY.png

The sheets are AutoCAD exports in which every filled area is split into triangles and the lettering
is drawn as outlines (no text to read). What is read from them:
  - rooms: the fills in the apartment colours (one colour per flat on a sheet) and the beige hatch of
    the stair / lift halls; the triangles of one colour are joined back into room polygons;
  - room names: from the outlined lettering (labels.py);
  - walls: the black fills (sheets of blocks Б-Д); on the block A sheets the walls are drawn as
    double lines, so there they are the strips between the rooms, with the doorways cut out at the
    door swings; columns and concrete walls: the closed blue / magenta outlines;
  - bathroom fittings: the brown outlines (baths, basins, toilets);
  - balcony doors: the orange door swings between a room and its loggia.
Windows are the stretches of a room's outline with no wall and no room across them (outside a
balcony door); on block A (a glass tower) they are floor-to-ceiling glazing. Plan coordinates are
metres in the block's own frame.
"""
import json
import math
import os
import sys
from collections import defaultdict

import pymupdf
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import polygonize, split, unary_union

sys.path.insert(0, os.path.dirname(__file__))
from labels import glyphs, room_name  # noqa: E402
import furniture  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
SHEETS = os.path.join(ROOT, '..', '00_Материалы_клиента', 'Планы')

R2 = lambda c: tuple(round(v, 2) for v in c) if c is not None else None

# Sheet -> plan frame. Axis positions on the sheet (pt) were read off the red axis lines.
# 'swap': the numbered axes run down the sheet and become the plan's x (the long side).
SHEET_INFO = {
    'BG': dict(file='ПЛАН-БЛОК -Б-Г.pdf', ax=(268.9, 616.0), ay=(146.4, 1119.4), size=(21.4, 60.0), swap=True,
               walls='fill', door_w=0.72, title='Блоки Б, В, Г, Д: этажи 3–18'),
    'BG_top': dict(file='ПЛАН БЛОК-Б-1-20-21-22.pdf', ax=(268.9, 616.0), ay=(146.4, 1119.4), size=(21.4, 60.0), swap=True,
                   walls='fill', door_w=0.72, title='Блоки Б и Г: этажи 19–22'),
    'A': dict(file='ПЛАН БЛОК-А -4-5-8-11-12-1314-15-16-19.pdf', ax=(145.9, 743.7), ay=(320.1, 917.9), size=(40.0, 40.0),
              swap=False, walls='gaps', door_w=0.42, title='Блок А: типовой этаж'),
    'A_t': dict(file='ПЛАН БЛОК-А 9-10-20-21.pdf', ax=(145.9, 743.7), ay=(320.1, 917.9), size=(40.0, 40.0),
                swap=False, walls='gaps', door_w=0.42, title='Блок А: этажи 9–10 и 20–21'),
}
SMALL_LOGGIA_AREA = 2.6  # m2: the small loggias are behind screens (no door needed)
MARGIN = 2.75  # m around the axes that still belongs to the plan (loggias); the flat labels are further out

IGNORE_FILL = {(1.0, 1.0, 1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 0.72), (0.01, 0.62, 0.13), (0.66, 0.06, 0.01),
               (0.41, 0.41, 0.41), (0.86, 0.86, 0.86), (0.98, 0.98, 0.98), (0.64, 0.28, 0.79), (0.0, 0.36, 0.72), (0.96, 0.96, 0.96)}
COMMON_FILL = {(0.98, 0.94, 0.82), (0.96, 0.33, 0.5)}   # stair / lift hall hatch, refuse room
WALL_FILL = (0.0, 0.0, 0.0)
STRUCT_STROKES = {(0.0, 0.12, 0.5), (1.0, 0.0, 1.0), (0.0, 0.0, 1.0)}  # columns (blue), concrete walls (magenta)
FIXTURE_STROKE = (0.65, 0.58, 0.4)
BALCONY_DOOR_STROKE = (1.0, 0.4, 0.0)

ROOM_NAMES = {  # kind -> (en, ru, tj)
    'living': ('Living room', 'Гостиная', 'Меҳмонхона'),
    'bedroom': ('Bedroom', 'Спальня', 'Хонаи хоб'),
    'kitchen': ('Kitchen', 'Кухня', 'Ошхона'),
    'hall': ('Hall', 'Холл', 'Даҳлез'),
    'bath': ('Bathroom', 'Ванная', 'Ҳаммом'),
    'wc': ('WC', 'Санузел', 'Ҳоҷатхона'),
    'storage': ('Wardrobe', 'Гардероб', 'Либосхона'),
    'loggia': ('Loggia', 'Лоджия', 'Айвон'),
    'terrace': ('Terrace', 'Терраса', 'Айвони кушод'),
}

# flat labels on the sheets: (rooms, area m2) as written next to each flat
LABELS = {
    'BG': [(3, 119.60)] * 2 + [(2, 75.77)] * 2 + [(2, 64.98)] * 2 + [(1, 67.57), (3, 145.18)] + [(3, 95.50)] * 2
          + [(2, 56.09)] * 2 + [(1, 36.63)] * 2 + [(2, 66.93)],
    'BG_top': [(3, 119.60)] * 2 + [(2, 75.77)] * 2 + [(2, 64.98)] * 2 + [(3, 145.18)] * 2 + [(3, 95.50)] * 2
              + [(2, 56.09)] * 2 + [(1, 36.63)] * 2,
    'A': [(3, 163.58)] * 2 + [(2, 98.41)] * 2 + [(2, 90.19)] * 2 + [(2, 90.95)] * 2 + [(4, 174.94)] * 2 + [(3, 134.74)] * 2,
    'A_t': [(3, 162.20)] * 2 + [(2, 97.73)] * 2 + [(4, 182.85)] * 2 + [(4, 173.47)] * 2 + [(3, 133.93)] * 2,
}
# name length in cap heights -> room (calibrated on all four sheets)
NAME_BY_LENGTH = [(2.0, 2.7, 'wc'), (3.2, 3.55, 'hall'), (3.6, 3.8, 'kitchen'), (3.8, 4.1, 'bath'), (4.5, 5.0, 'storage'),
                  (5.1, 5.6, 'bedroom'), (6.2, 6.9, 'living')]


# ----------------------------------------------------------------------------
# geometry helpers
# ----------------------------------------------------------------------------

def parts(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == 'Polygon':
        return [g]
    return [q for q in getattr(g, 'geoms', []) if q.geom_type == 'Polygon']


def ring(poly, nd=3):
    p = poly.simplify(0.01, preserve_topology=True)
    c = list(p.exterior.coords)[:-1]
    if not Polygon(c).exterior.is_ccw:
        c = c[::-1]
    return [[round(x, nd), round(y, nd)] for x, y in c]


def no_holes(p, depth=0):
    """Split a polygon through its holes until none is left (the viewer extrudes outer rings).
    The cut goes through a point inside the hole (the centroid of an L- or U-shaped hole can lie
    outside it, and a cut there would miss the hole and leave it to be filled in)."""
    if p.geom_type != 'Polygon' or not p.interiors:
        return [p]
    c = Polygon(p.interiors[0]).representative_point()
    x0, y0, x1, y1 = p.bounds
    pieces = list(split(p, LineString([(c.x, y0 - 1), (c.x, y1 + 1)])).geoms)
    if len(pieces) < 2 or depth > 40:
        # vertical cut failed: try a horizontal one through the same point
        pieces = list(split(p, LineString([(x0 - 1, c.y), (x1 + 1, c.y)])).geoms)
        if len(pieces) < 2:
            raise ValueError('cannot split a polygon with a hole')
    out = []
    for q in pieces:
        out += no_holes(q, depth + 1)
    return out


def snap(g, grid=0.01):
    return shapely.set_precision(g, grid)


def min_width(p):
    c = list(p.minimum_rotated_rectangle.exterior.coords)
    return min(math.dist(c[0], c[1]), math.dist(c[1], c[2]))


# ----------------------------------------------------------------------------
# reading a sheet
# ----------------------------------------------------------------------------

class Sheet:
    def __init__(self, key):
        info = SHEET_INFO[key]
        self.key, self.info = key, info
        self.pg = pymupdf.open(os.path.join(SHEETS, info['file']))[0]
        (ax0, ax1), (ay0, ay1) = info['ax'], info['ay']
        w, h = info['size']
        self.s = ((ax1 - ax0) / w + (ay1 - ay0) / h) / 2  # pt per metre
        self.cx, self.cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
        sw = (ax1 - ax0) / 2 + MARGIN * self.s
        sh = (ay1 - ay0) / 2 + MARGIN * self.s
        self.region = pymupdf.Rect(self.cx - sw, self.cy - sh, self.cx + sw, self.cy + sh)
        self.drawings = [d for d in self.pg.get_drawings() if self.region.contains(d['rect'])]
        self._fills = None

    def P(self, p):
        """sheet point -> plan metres"""
        dx, dy = (p[0] - self.cx) / self.s, (p[1] - self.cy) / self.s
        if self.info['swap']:
            return (round(dy, 4), round(dx, 4))
        return (round(dx, 4), round(-dy, 4))

    def path_points(self, d, keep_curves=False, close_rects=False):
        """Sub-paths of a drawing as lists of plan points (curves flattened); close_rects: a
        rectangle with its fourth side too (a closed outline)"""
        subs, cur, curves = [], [], []
        for it in d['items']:
            k = it[0]
            if k in ('re', 'qu'):
                if cur:
                    subs.append(cur)
                    cur = []
                q = it[1].quad if k == 're' else it[1]
                subs.append([q.ul, q.ur, q.lr, q.ll] + ([q.ul] if close_rects else []))
                continue
            p0 = it[1]
            if cur and (abs(cur[-1].x - p0.x) > 1e-3 or abs(cur[-1].y - p0.y) > 1e-3):
                subs.append(cur)
                cur = []
            if not cur:
                cur = [p0]
            if k == 'l':
                cur.append(it[2])
            else:  # bezier
                b = it[1:5]
                curves.append([self.P((q.x, q.y)) for q in b])
                for i in range(1, 9):
                    t = i / 8
                    w = ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3)
                    cur.append(pymupdf.Point(sum(a * q.x for a, q in zip(w, b)), sum(a * q.y for a, q in zip(w, b))))
        if cur:
            subs.append(cur)
        pts = [[self.P((p.x, p.y)) for p in s] for s in subs]
        return (pts, curves) if keep_curves else pts

    def fills(self):
        """Filled areas by colour, as they show on the sheet: what a later fill paints over is gone
        (the sheets draw a wall and then a room's fill over part of it, e.g. in some bathrooms)."""
        if self._fills is None:
            seq = []
            for d in self.drawings:
                f = R2(d.get('fill'))
                if f is None:
                    continue
                shape = None
                for s in self.path_points(d):
                    if len(s) >= 3:
                        g = Polygon(s).buffer(0)
                        if g.area > 1e-6:
                            shape = g if shape is None else (shape.symmetric_difference(g) if d.get('even_odd') else shape.union(g))
                if shape is not None and not shape.is_empty:
                    seq.append((f, shape.buffer(0)))
            import shapely
            covers = [i for i, (f, g) in enumerate(seq) if f not in IGNORE_FILL or f in COMMON_FILL]
            tree = shapely.STRtree([seq[i][1] for i in covers])
            by = defaultdict(list)
            for i, (f, g) in enumerate(seq):
                if f == WALL_FILL:
                    later = [seq[covers[j]][1] for j in tree.query(g) if covers[j] > i]
                    if later:
                        g = g.difference(unary_union(later).buffer(0.002))
                by[f] += [q for q in parts(g) if q.area > 1e-6]
            self._fills = by
            return by
        if False:
            by = defaultdict(list)
            for d in self.drawings:
                f = R2(d.get('fill'))
                if f is None:
                    continue
                # the sub-paths of one fill: even-odd fills (a wall drawn as an outer and an inner
                # ring) are the rings XOR'd, else their union
                shape = None
                for s in self.path_points(d):
                    if len(s) >= 3:
                        g = Polygon(s).buffer(0)
                        if g.area > 1e-6:
                            shape = g if shape is None else (shape.symmetric_difference(g) if d.get('even_odd') else shape.union(g))
                if shape is not None:
                    by[f] += [q for q in parts(shape.buffer(0)) if q.area > 1e-6]
            self._fills = by
        return self._fills

    def strokes(self, colour, width=None, curves=False, close_rects=False):
        out = []
        for d in self.drawings:
            if R2(d.get('color')) != colour:
                continue
            if width is not None and abs((d.get('width') or 0) - width) > 0.02:
                continue
            if curves:
                out.append(self.path_points(d, keep_curves=True))
            else:
                out += [s for s in self.path_points(d, close_rects=close_rects) if len(s) >= 2]
        return out


def door_symbols(sh, gaps, room_geom, swings=None):
    """Doorways from the door symbols (block A sheets draw them as short strokes: leaf, swing,
    ticks at the jambs). Each symbol is a door-sized cluster of strokes against a wall: the doorway is
    its extent along that wall, cut through the whole wall thickness. Only between rooms of one flat,
    or from a flat to the stair / lift hall, never through a wall between two flats."""
    segs = [LineString(s) for s in sh.strokes((0.0, 0.0, 0.0), sh.info['door_w']) if len(s) >= 2]
    blobs = parts(unary_union([q.buffer(0.04) for q in segs]))
    colour_at = []
    for c, g in room_geom.items():
        colour_at.append((c, g))

    def colour(pt):
        for c, g in colour_at:
            if g.buffer(0.02).contains(pt):
                return c
        return None
    out = []
    for b in blobs:
        r = b.minimum_rotated_rectangle
        cs = list(r.exterior.coords)
        e = sorted([math.dist(cs[0], cs[1]), math.dist(cs[1], cs[2])])
        if not (0.45 <= e[1] <= 1.6 and e[0] <= 1.3):
            continue
        near = gaps.intersection(b.buffer(0.45))
        if near.is_empty or near.area < 0.02:
            continue
        wr = near.minimum_rotated_rectangle
        wc = list(wr.exterior.coords)
        d1 = (wc[1][0] - wc[0][0], wc[1][1] - wc[0][1])
        d2 = (wc[2][0] - wc[1][0], wc[2][1] - wc[1][1])
        d = d1 if math.hypot(*d1) >= math.hypot(*d2) else d2
        L = math.hypot(*d) or 1.0
        ux, uy = d[0] / L, d[1] / L
        nx, ny = -uy, ux
        o = near.centroid
        ss = [(p[0] - o.x) * ux + (p[1] - o.y) * uy for p in b.exterior.coords]
        s0, s1 = min(ss) + 0.03, max(ss) - 0.03
        if s1 - s0 < 0.55:
            continue
        sm = (s0 + s1) / 2
        mid = (o.x + ux * sm, o.y + uy * sm)
        sides = [colour(Point(mid[0] + nx * k, mid[1] + ny * k)) for k in (0.55, -0.55)]
        if None in sides:
            continue
        common = [c in COMMON_FILL for c in sides]
        if sides[0] != sides[1] and not any(common):
            continue  # a wall between two flats
        T = 0.6
        if swings is not None:
            # the side the door opens to: where the leaf and its swing are drawn
            side = (b.centroid.x - mid[0]) * nx + (b.centroid.y - mid[1]) * ny
            if abs(side) > 0.08:
                k = 0.5 if side > 0 else -0.5
                swings.append((round(mid[0], 3), round(mid[1], 3), round(mid[0] + nx * k, 3), round(mid[1] + ny * k, 3)))
        out.append(Polygon([(o.x + ux * s0 + nx * T, o.y + uy * s0 + ny * T), (o.x + ux * s1 + nx * T, o.y + uy * s1 + ny * T),
                            (o.x + ux * s1 - nx * T, o.y + uy * s1 - ny * T), (o.x + ux * s0 - nx * T, o.y + uy * s0 - ny * T)]))
    return out


def door_arcs(sh):
    """The swings of the doors drawn as polylines (black, any width): a run of points on a circle of
    0.5-1.15 m (the leaf), 25-100 degrees of it (doors are drawn part open). {c: the hinge, r, mid:
    the middle of the arc}"""
    import numpy as np
    out = []
    for d in sh.drawings:
        if R2(d.get('color')) != (0.0, 0.0, 0.0):
            continue
        for s in sh.path_points(d):
            if len(s) < 4:
                continue
            P = np.array(s)
            x, y = P[:, 0], P[:, 1]
            sol = np.linalg.lstsq(np.c_[2 * x, 2 * y, np.ones(len(P))], x * x + y * y, rcond=None)[0]
            cx, cy = sol[0], sol[1]
            r = math.sqrt(max(sol[2] + cx * cx + cy * cy, 0.0))
            if not 0.5 <= r <= 1.15 or np.abs(np.hypot(x - cx, y - cy) - r).max() > 0.02:
                continue
            a0, a1 = math.atan2(y[0] - cy, x[0] - cx), math.atan2(y[-1] - cy, x[-1] - cx)
            span = abs((a1 - a0 + math.pi) % (2 * math.pi) - math.pi)
            if not math.radians(25) <= span <= math.radians(100):
                continue
            m = s[len(s) // 2]
            out.append(dict(c=(float(cx), float(cy)), r=r, mid=(m[0], m[1])))
    return out


def door_openings(sh, walls_hint):
    """Doorways from the door swings: a quarter arc round the hinge, from the leaf tip to the jamb.
    Returns the opening rectangles (across the wall) as polygons."""
    out = []
    for pts, curves in sh.strokes((0.0, 0.0, 0.0), sh.info['door_w'], curves=True):
        for b in curves:
            p0, c1, c2, p3 = b
            chord = math.dist(p0, p3)
            r = chord / math.sqrt(2)
            if not (0.55 <= r <= 1.25):
                continue
            # the two possible centres of a quarter circle through p0 and p3; the arc bulges away from it
            mx, my = (p0[0] + p3[0]) / 2, (p0[1] + p3[1]) / 2
            ux, uy = (p3[0] - p0[0]) / chord, (p3[1] - p0[1]) / chord
            nx, ny = -uy, ux
            h = chord / 2
            bulge = ((c1[0] + c2[0]) / 2 - mx) * nx + ((c1[1] + c2[1]) / 2 - my) * ny
            sgn = -1 if bulge > 0 else 1
            C = (mx + nx * h * sgn, my + ny * h * sgn)
            # the closed end of the leaf lies in the wall line: the arc end nearer the walls / gaps
            d0 = walls_hint.distance(Point(p0))
            d3 = walls_hint.distance(Point(p3))
            E = p0 if d0 < d3 else p3
            L = math.dist(C, E)
            ex, ey = (E[0] - C[0]) / L, (E[1] - C[1]) / L
            qx, qy = -ey, ex
            T = 0.45
            out.append(Polygon([(C[0] + qx * T, C[1] + qy * T), (E[0] + qx * T, E[1] + qy * T),
                                (E[0] - qx * T, E[1] - qy * T), (C[0] - qx * T, C[1] - qy * T)]))
    return out


def drop_lettering(walls, struct):
    """Black lettering on the sheets (the lift capacities "Q=1000 кг", dimensions) is filled the
    same black as the walls: clusters of small pieces that touch no real wall are taken out."""
    comps = parts(walls)
    big = unary_union([c for c in comps if c.area >= 0.3] + [struct])
    small = [c for c in comps if c.area < 0.3]
    clusters = parts(unary_union([c.buffer(0.15) for c in small])) if small else []
    drop = []
    for cl in clusters:
        mine = [c for c in small if cl.contains(c.representative_point())]
        total = sum(c.area for c in mine)
        if len(mine) >= 2 and total < 0.5 and all(c.area < 0.06 for c in mine) and min(c.distance(big) for c in mine) > 0.03:
            drop += mine
    if drop:
        walls = walls.difference(unary_union([c.buffer(0.002) for c in drop]))
        print('  lettering left out: %d pieces' % len(drop))
    return walls


# fills a sheet leaves out where the other sheet of the same block has them: the sheet of block
# A's terrace floors draws one bathroom (C/У 3,45 m2 of the north-east flat) white, the typical
# floor's sheet has its colour (the walls of block A are the strips between the coloured rooms)
BORROW_FILLS = {'A_t': [('A', (13.6, 15.0))]}


def extract(key):
    sh = Sheet(key)
    by = sh.fills()
    for src, pt in BORROW_FILLS.get(key, []):
        for c, ps in Sheet(src).fills().items():
            if c in IGNORE_FILL or c in COMMON_FILL:
                continue
            room = [q for q in parts(unary_union([p.buffer(0.002) for p in ps]).buffer(-0.002)) if q.contains(Point(*pt))]
            if room and not any(p.contains(Point(*pt)) for p in by.get(c, [])):
                by[c] = list(by.get(c, [])) + room
                print('  %s: the fill at %.1f, %.1f taken from sheet %s (%.2f m2)' % (key, pt[0], pt[1], src, room[0].area))

    apt_colours = [c for c, ps in by.items() if c not in IGNORE_FILL and c not in COMMON_FILL and sum(p.area for p in ps) > 3.0]
    room_geom = {}
    for c in apt_colours + [c for c in COMMON_FILL if c in by]:
        room_geom[c] = snap(unary_union([p.buffer(0.004) for p in by[c]]).buffer(-0.004))

    # columns and concrete walls: closed outlines
    def struct_of(close_rects):
        lines = [LineString(s) for col in STRUCT_STROKES for s in sh.strokes(col, close_rects=close_rects)]
        # (letters drawn in the same blue - the lift capacities "Q=1000 кг" - are no columns: they
        # are small and far from solid, a column or a wall piece is a near rectangle)
        out = [p for p in polygonize(unary_union(lines))
               if p.area > 0.03 and not (p.area < 0.6 and p.area < 0.75 * p.minimum_rotated_rectangle.area)]
        return snap(unary_union([p.buffer(0.005) for p in out]))
    # the pieces drawn as rectangles (the hatched partitions a TV hangs on, between a bedroom and
    # its loggia) are walls too; the rooms are cut out as before, by the outlines drawn as lines -
    # the rectangles' outlines lie over the rooms' fills and would shave their areas off the sheet's
    struct = struct_of(True)
    struct_rooms = struct_of(False)

    rooms_all = unary_union(list(room_geom.values()))
    fill_walls = snap(unary_union([p.buffer(0.004) for p in by.get(WALL_FILL, [])]).buffer(-0.004))
    doors = []
    outline_walls = Polygon()
    if sh.info['walls'] == 'gaps':
        # walls are the strips between the rooms (up to 0.7 m), less the doorways
        closed = rooms_all.buffer(0.35, join_style='mitre').buffer(-0.35, join_style='mitre')
        gaps = closed.difference(rooms_all)
        doors = door_symbols(sh, gaps, room_geom)
        walls = gaps.difference(unary_union(doors)) if doors else gaps
        # where two room fills touch, the wall between them is only its two outlines (thin grey
        # lines, partitions in black): the thin cells between those lines are walls too
        outline_lines = [LineString(s) for s in sh.strokes((0.41, 0.41, 0.41), 0.06)] + \
                        [LineString(s) for s in sh.strokes((0.0, 0.0, 0.0), 0.84)]
        # (inside the plan only: the facade is the curtain wall, read from the room outlines)
        prov = unary_union([rooms_all, gaps]).buffer(0.45, join_style='mitre').buffer(-0.45, join_style='mitre')
        prov = max(parts(prov), key=lambda q: q.area)
        facade_band = prov.exterior.buffer(0.8)
        thin = [q for q in polygonize(unary_union(outline_lines))
                if q.area > 0.02 and 2 * q.area / q.length < 0.32 and not q.intersects(facade_band)
                and q.intersection(rooms_all).area > 0.3 * q.area]
        if thin:
            ow = unary_union([q.buffer(0.01) for q in thin])
            if doors:
                ow = ow.difference(unary_union(doors))
            outline_walls = ow
            walls = unary_union([walls, ow])
        walls = unary_union([walls, fill_walls])
        walls = unary_union([g for g in parts(walls.buffer(-0.02).buffer(0.02)) if g.area > 0.02])
    else:
        walls = fill_walls
        # doors drawn over a wall line (the wall runs on under the door leaf): cut at the door symbol
        closed = rooms_all.buffer(0.35, join_style='mitre').buffer(-0.35, join_style='mitre')
        gaps = closed.difference(rooms_all)
        doors = door_symbols(sh, gaps, room_geom)
        keep_w = sh.info['door_w']
        sh.info['door_w'] = 0.84
        doors += door_symbols(sh, gaps, room_geom)
        sh.info['door_w'] = keep_w
        if doors:
            # only through the wall between the two rooms (not along it into the next room)
            cut = unary_union(doors).intersection(gaps.buffer(0.02))
            walls = walls.difference(cut)
    walls = snap(walls.difference(struct))
    walls = drop_lettering(walls, struct)

    everything = unary_union([walls, struct, rooms_all])
    enclosure = everything.buffer(0.45, join_style='mitre').buffer(-0.45, join_style='mitre')
    enclosure = max(parts(enclosure), key=lambda q: q.area)
    outside = box(*enclosure.buffer(5).bounds).difference(enclosure)

    rooms = []
    # a room is its fill less the walls and shafts drawn over it (some fills run on under a shaft);
    # columns standing inside a room stay part of it (the viewer draws them in the room)
    solid = unary_union([walls, struct])
    for c, g0 in room_geom.items():
        g = g0.difference(walls).difference(struct_rooms.buffer(0.01)) if not g0.is_empty else g0
        for q in parts(g.buffer(-0.02).buffer(0.02)):
            q = Polygon(q.exterior) if q.interiors and all(Polygon(h).area < 2.5 for h in q.interiors) else q
            if q.area >= 0.6:
                # the fill as drawn (before the walls drawn over it): what the sheet's areas are of
                fill = sum(f.area for f in parts(g0) if f.buffer(0.3).intersects(q.representative_point().buffer(0.01)) and f.intersection(q).area > 0.5 * q.area)
                rooms.append(dict(colour=c, poly=q, common=c in COMMON_FILL, fill_area=fill or q.area))

    fixtures = parts(unary_union([LineString(s).buffer(0.03) for s in sh.strokes(FIXTURE_STROKE)]))
    fixtures = [p.minimum_rotated_rectangle for p in fixtures if p.area > 0.05]
    doors_balc = [LineString(s) for s in sh.strokes(BALCONY_DOOR_STROKE, 0.42) if len(s) >= 2]
    arcs = door_arcs(sh)

    gl = glyphs(by)
    for r in rooms:
        p = r['poly']
        r['area'] = p.area
        r['outer'] = p.buffer(0.6).intersection(outside).area
        r['fix'] = [f for f in fixtures if p.contains(f.centroid)]
        r['width'] = min_width(p)
        r['label'] = room_name(p, gl)
        r['kind'] = classify(r)
    # the outlines between a room and its loggia or terrace are the glass front (block A): no wall
    # (the small service balconies keep their drawn walls)
    air = unary_union([r['poly'] for r in rooms if r['kind'] in ('loggia', 'terrace') and r['area'] > SMALL_LOGGIA_AREA])
    if not outline_walls.is_empty and not air.is_empty:
        walls = snap(walls.difference(outline_walls.intersection(air.buffer(0.45))))
    return sh, dict(rooms=rooms, walls=walls, struct=struct, enclosure=enclosure, outside=outside, fixtures=fixtures,
                    doors_balc=doors_balc, doors=doors, apt_colours=apt_colours, arcs=arcs)


def classify(r):
    """Room kind from its written name (labels.py), with the drawing as a fallback."""
    if r['common']:
        return 'common'
    nm = r['label'] and r['label'].get('name')
    kind = None
    if nm:
        for lo, hi, k in NAME_BY_LENGTH:
            if lo <= nm['rel'] <= hi:
                kind = k
        if kind == 'wc' and any(f.area > 0.9 for f in r['fix']):
            kind = 'bath'   # "С/У" with a bath tub: a combined bathroom
    if kind:
        return kind
    if r['fix']:
        return 'bath' if any(f.area > 0.9 for f in r['fix']) or r['area'] >= 3.2 else 'wc'
    if r['outer'] > 0.1:
        return 'terrace' if r['area'] > 7.5 else 'loggia'
    return 'storage' if r['area'] < 7.0 else 'hall'


def group_apartments(key, x):
    """Rooms of one colour that meet across a wall are one flat; match each flat to a sheet label."""
    flats = []
    for c in x['apt_colours']:
        rs = [r for r in x['rooms'] if r['colour'] == c]
        blob = unary_union([r['poly'].buffer(0.42, join_style='mitre') for r in rs])
        for q in parts(blob):
            mine = [r for r in rs if q.contains(r['poly'].representative_point())]
            if mine and sum(r['area'] for r in mine) >= 20:
                flats.append(dict(colour=c, rooms=mine))
    labels = list(LABELS[key])
    for f in flats:
        f['rooms_count'] = sum(1 for r in f['rooms'] if r['kind'] in ('bedroom', 'living'))
        f['drawn_area'] = sum(r['area'] for r in f['rooms'])
        f['fill_area'] = sum(r.get('fill_area', r['area']) for r in f['rooms'])
    pairs = sorted(((abs(f['fill_area'] - a) + (0 if n == f['rooms_count'] else 25), i, j)
                    for i, f in enumerate(flats) for j, (n, a) in enumerate(labels)))
    used_f, used_l = set(), set()
    for cost, i, j in pairs:
        if i in used_f or j in used_l:
            continue
        used_f.add(i)
        used_l.add(j)
        flats[i]['label'] = labels[j]
    return flats


def tower_glazing(x):
    """Block A is glazed floor to ceiling: every stretch of a room's outline that looks out (the
    facade, or a loggia / terrace across it) is glass, whatever the drawing's wall lines say, but
    for the doors to the terraces (one door from a room to each terrace: at the drawn swing, else in
    the middle of its longest glass) and the columns. The small loggias (service balconies) keep
    their drawn walls and door. Returns the glazing pieces; the walls under them are taken out."""
    rooms = x['rooms']
    struct = x['struct']
    outside = x['outside']
    air_rooms = [r for r in rooms if r['kind'] in ('loggia', 'terrace') and r['poly'].area > SMALL_LOGGIA_AREA]
    small_air = [r for r in rooms if r['kind'] in ('loggia', 'terrace') and r['poly'].area <= SMALL_LOGGIA_AREA]
    flat_of = {id(r): fi for fi, f in enumerate(x.get('flats', [])) for r in f['rooms']}
    door_swings = unary_union([d.buffer(0.05) for d in x['doors_balc']]) if x['doors_balc'] else Polygon()
    pieces, cuts, door_runs = [], [], {}
    for r in rooms:
        if r['common'] or r['kind'] in ('loggia', 'terrace', 'bath', 'wc', 'storage', 'hall'):
            continue
        p = r['poly'].simplify(0.02)
        cs = list(p.exterior.coords)
        if not p.exterior.is_ccw:
            cs = cs[::-1]
        for a, b in zip(cs, cs[1:]):
            L = math.dist(a, b)
            if L < 0.3:
                continue
            ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            nx, ny = uy, -ux   # outward
            n = max(1, int(L / 0.1))
            run = None
            for i in range(n + 1):
                t = min(L, i * L / n)
                q = (a[0] + ux * t, a[1] + uy * t)
                probe = LineString([(q[0] + nx * 0.02, q[1] + ny * 0.02), (q[0] + nx * 0.9, q[1] + ny * 0.9)])
                hit_out = probe.intersects(outside)
                mine = flat_of.get(id(r))
                hit_air = next((ar for ar in air_rooms if probe.intersects(ar['poly']) and flat_of.get(id(ar)) == mine), None)
                # anything else across (another room, or another flat's loggia): no glass here
                other = any(o is not r and o is not hit_air and probe.intersects(o['poly']) and
                            (o['kind'] not in ('loggia', 'terrace') or flat_of.get(id(o)) != mine or o in small_air) for o in rooms)
                ok = (hit_out or hit_air) and not other
                if ok and run is None:
                    run = [t, t, hit_air]
                elif ok:
                    run[1] = t
                if (not ok or i == n) and run is not None:
                    t0, t1, air = run
                    run = None
                    if t1 - t0 < 0.4:
                        continue
                    depth = 0.9 if not air else max(0.15, min(0.9, air['poly'].distance(Point(a[0] + ux * (t0 + t1) / 2, a[1] + uy * (t0 + t1) / 2)) + 0.02))
                    g0 = (a[0] + ux * t0, a[1] + uy * t0)
                    g1 = (a[0] + ux * t1, a[1] + uy * t1)
                    poly = Polygon([g0, g1, (g1[0] + nx * depth, g1[1] + ny * depth), (g0[0] + nx * depth, g0[1] + ny * depth)])
                    if not air:
                        poly = poly.difference(outside.buffer(-0.01))   # up to the facade line
                    else:
                        poly = poly.difference(air['poly'])
                        span = LineString([g0, g1])
                        d = door_swings.intersection(span.buffer(0.9)) if not door_swings.is_empty else Polygon()
                        door_runs.setdefault((id(r), id(air)), []).append(dict(poly=poly, span=span, swing=d))
                        continue
                    poly = poly.difference(struct)
                    pieces += [g for g in parts(poly) if g.area > 0.03]
    # one door from a room to each terrace: at the drawn swing (the longest such run), else in the
    # middle of the longest run of glass; the other runs are glass all along
    for runs in door_runs.values():
        swung = [g for g in runs if not g['swing'].is_empty]
        at = max(swung or runs, key=lambda g: g['span'].length)
        for g in runs:
            poly = g['poly']
            if g is at:
                span = g['span']
                c = span.interpolate(span.project(g['swing'].centroid)) if not g['swing'].is_empty else span.interpolate(0.5, normalized=True)
                cut = c.buffer(0.46, cap_style='square')
                cuts.append(poly.intersection(cut).buffer(0.03))
                poly = poly.difference(cut)
            poly = poly.difference(struct)
            pieces += [h for h in parts(poly) if h.area > 0.03]
    return pieces, cuts


def openings(key, x):
    """Windows: free stretches of a room's outline (no wall on it) with no room across them, or with a
    loggia across them (less the balcony door). Block A's outer windows are floor-to-ceiling glazing."""
    rooms = x['rooms']
    W = unary_union([x['walls'], x['struct']])
    Wb = W.buffer(0.04)
    allrooms = unary_union([r['poly'] for r in rooms])
    doors = unary_union([d.buffer(0.05) for d in x['doors_balc']]) if x['doors_balc'] else None
    glass_tower = key.startswith('A')
    open_air = ('loggia', 'terrace')
    wins, glaz = [], []
    door_to, candidates = set(), []
    for r in rooms:
        p = r['poly'].simplify(0.02)
        cs = list(p.exterior.coords)
        if not p.exterior.is_ccw:
            cs = cs[::-1]
        for a, b in zip(cs, cs[1:]):
            seg = LineString([a, b])
            if seg.length < 0.35:
                continue
            free = seg.difference(Wb)
            for f in getattr(free, 'geoms', [free]):
                if f.is_empty or f.length < 0.4 or f.geom_type != 'LineString':
                    continue
                dx, dy = b[0] - a[0], b[1] - a[1]
                L = math.hypot(dx, dy)
                n = (dy / L, -dx / L)  # outward (CCW ring: inside on the left)
                fa, fb = f.coords[0], f.coords[-1]
                strip = Polygon([fa, fb, (fb[0] + n[0] * 0.7, fb[1] + n[1] * 0.7), (fa[0] + n[0] * 0.7, fa[1] + n[1] * 0.7)])
                across = [q for q in rooms if q is not r and strip.intersection(q['poly']).area > 0.03]
                mine_air = r['kind'] in open_air
                if across:
                    air = [q for q in across if q['kind'] in open_air]
                    if mine_air or not air or len(air) != len(across):
                        continue  # a doorway between rooms (the viewer puts a door there), or seen from the loggia
                    if glass_tower and f.length <= 1.3 and all(q['poly'].area <= SMALL_LOGGIA_AREA for q in air):
                        door_to.add(id(air[0]))
                        continue  # block A's service balconies: walls and a door, the door's gap no window
                    if f.length <= 1.3 and all(q['poly'].area <= SMALL_LOGGIA_AREA for q in air):
                        # a service loggia with its door drawn (the leaf's swing at the gap): a doorway,
                        # opening the way the drawing has it
                        arc = next((q for q in x.get('arcs', []) if f.distance(Point(q['c'])) < 0.35 and q['r'] <= f.length + 0.35), None)
                        if arc:
                            door_to.add(id(air[0]))
                            m = f.interpolate(0.5, normalized=True)
                            k = 0.5 if (arc['mid'][0] - m.x) * n[0] + (arc['mid'][1] - m.y) * n[1] > 0 else -0.5
                            x.setdefault('swings', []).append((round(m.x, 3), round(m.y, 3), round(m.x + n[0] * k, 3), round(m.y + n[1] * k, 3)))
                            continue
                elif mine_air and (glass_tower or r['kind'] == 'terrace'):
                    continue  # the open edge of a balcony or terrace: a railing, not a window
                # how far out the wall reaches next to the opening
                T = 0.0
                for end in (fa, fb):
                    near = W.intersection(Point(end).buffer(0.45))
                    for g in parts(near):
                        for c in g.exterior.coords:
                            T = max(T, (c[0] - end[0]) * n[0] + (c[1] - end[1]) * n[1])
                if across:
                    T = across[0]['poly'].distance(seg)
                    T = T if T > 0.05 else 0.25
                T = min(max(T, 0.2), 0.55)
                spans = [(0.0, f.length)]
                ux, uy = (fb[0] - fa[0]) / f.length, (fb[1] - fa[1]) / f.length
                if across and doors is not None:
                    d = doors.intersection(strip.buffer(0.9))
                    if not d.is_empty:
                        cut = []
                        for g in parts(d):
                            ss = [((c[0] - fa[0]) * ux + (c[1] - fa[1]) * uy) for c in g.exterior.coords]
                            lo, hi = min(ss), max(ss)
                            if hi - lo > 0.4:
                                # the swing spans the leaf: that is the door, 0.8-1.0 m wide
                                m, w = (lo + hi) / 2, min(max(hi - lo, 0.8), 1.0)
                                lo, hi = m - w / 2, m + w / 2
                                if lo < 0:
                                    lo, hi = 0.0, min(f.length, w)
                                if hi > f.length:
                                    lo, hi = max(0.0, f.length - w), f.length
                                cut.append((lo, hi))
                        if cut:
                            cut.sort()
                            spans, at = [], 0.0
                            for lo, hi in cut:
                                spans.append((at, lo - 0.02))
                                at = hi + 0.02
                            spans.append((at, f.length))
                            door_to.add(id(across[0]))
                if across:
                    candidates.append((f.length, id(across[0]), across[0], r, fa, fb, n, T, len(wins)))
                for s0, s1 in spans:
                    if s1 - s0 < 0.4:
                        continue
                    q0 = (fa[0] + ux * s0, fa[1] + uy * s0)
                    q1 = (fa[0] + ux * s1, fa[1] + uy * s1)
                    poly = Polygon([q0, q1, (q1[0] + n[0] * T, q1[1] + n[1] * T), (q0[0] + n[0] * T, q0[1] + n[1] * T)])
                    poly = poly.difference(allrooms.buffer(-0.005)).difference(W)
                    for g in parts(poly):
                        if g.area > 0.04:
                            (glaz if glass_tower and not mine_air else wins).append(g)
    # a loggia that the drawing gives no door to (only windows from the rooms): a balcony door in
    # the middle of its longest window, so it can be walked onto
    best = {}
    for c in candidates:
        if c[1] not in door_to and c[2]['area'] > SMALL_LOGGIA_AREA and (c[1] not in best or c[0] > best[c[1]][0]):
            best[c[1]] = c
    for length, _, lg, r, fa, fb, n, T, _ in best.values():
        if length < 0.6:
            continue
        ux, uy = (fb[0] - fa[0]) / length, (fb[1] - fa[1]) / length
        m = length / 2
        hw = 0.45 if length >= 1.3 else length / 2 + 0.05  # a short opening becomes the door as a whole
        cut = Polygon([(fa[0] + ux * (m - hw) - n[0] * 0.3, fa[1] + uy * (m - hw) - n[1] * 0.3),
                       (fa[0] + ux * (m + hw) - n[0] * 0.3, fa[1] + uy * (m + hw) - n[1] * 0.3),
                       (fa[0] + ux * (m + hw) + n[0] * (T + 0.3), fa[1] + uy * (m + hw) + n[1] * (T + 0.3)),
                       (fa[0] + ux * (m - hw) + n[0] * (T + 0.3), fa[1] + uy * (m - hw) + n[1] * (T + 0.3))])
        out = []
        for w in wins:
            if w.intersects(cut):
                out += [g for g in parts(w.difference(cut)) if g.area > 0.04]
            else:
                out.append(w)
        wins = out
    return wins, glaz


def doorways(x):
    """Free stretches of room outlines (no wall, no window) with another room across: the doorways."""
    W = unary_union([x['walls'], x['struct']] + list(x['windows']) + list(x['glazing'])).buffer(0.04)
    out = []
    rooms = x['rooms']
    for r in rooms:
        free = r['poly'].exterior.difference(W)
        for f in getattr(free, 'geoms', [free]):
            if f.is_empty or f.length < 0.45 or f.geom_type != 'LineString':
                continue
            probe = f.buffer(0.35)
            if any(q is not r and probe.intersection(q['poly']).area > 0.02 for q in rooms):
                out.append(f)
    return out


def facing(r, free, rooms, step=0.1, depth=0.6):
    """Split the free stretches of room r's outline by what lies across them: [(room or None, line)].
    Each 10 cm piece looks 0.6 m out from the room (the outline runs counter-clockwise, the room on
    its left) and takes the room it overlaps most."""
    out = []
    for f in getattr(free, 'geoms', [free]):
        if f.is_empty or f.geom_type != 'LineString' or f.length < 0.15:
            continue
        n = max(1, int(round(f.length / step)))
        run_q, run_pts = 'start', []
        ccw = r['poly'].exterior.is_ccw
        for i in range(n):
            a = f.interpolate(i / n, normalized=True)
            b = f.interpolate((i + 1) / n, normalized=True)
            dx, dy = b.x - a.x, b.y - a.y
            L = math.hypot(dx, dy) or 1e-9
            nx, ny = (dy / L, -dx / L) if ccw else (-dy / L, dx / L)
            probe = Polygon([(a.x, a.y), (b.x, b.y), (b.x + nx * depth, b.y + ny * depth), (a.x + nx * depth, a.y + ny * depth)])
            best, ba = None, 0.004
            for q in rooms:
                if q is r:
                    continue
                ar = probe.intersection(q['poly']).area
                if ar > ba:
                    best, ba = q, ar
            if best is not run_q and run_pts:
                out.append((run_q, LineString(run_pts)))
                run_pts = []
            if not run_pts:
                run_pts = [(a.x, a.y)]
            run_pts.append((b.x, b.y))
            run_q = best
        if len(run_pts) >= 2:
            out.append((run_q, LineString(run_pts)))
    return out


def tidy_doors(sh, x):
    """One way between two rooms, and only where the drawing has it.

    The walls read off the sheet leave gaps (a wall drawn in another colour, a party wall that is
    only a line, the end of a fill short of the wall): each gap between two rooms would be another
    doorway. Every opening between two rooms is listed, then:
      - between two flats (rooms, loggias or terraces): walled up;
      - between two rooms of a flat, or a flat and the stair hall: one per pair, the one with a door
        symbol on the drawing, else the most door-like;
      - an opening with no door symbol that is not open plan (up to 1.4 m) is walled up too, as long
        as every room of the flat can still be reached from the stair hall without it.
    Openings from a room to its own loggia or terrace are left to the windows and balcony doors."""
    rooms = x['rooms']
    flat_of = {}
    for fi, f in enumerate(x['flats']):
        for r in f['rooms']:
            flat_of[id(r)] = fi
    # rooms that are in no flat (a small fill of its own colour): the flat of the room they open to
    for r in rooms:
        if id(r) in flat_of or r['common']:
            continue
        near = sorted((q for q in rooms if id(q) in flat_of), key=lambda q: q['poly'].distance(r['poly']))
        if near and near[0]['poly'].distance(r['poly']) < 0.6:
            flat_of[id(r)] = flat_of[id(near[0])]
    room_geom = defaultdict(list)
    for r in rooms:
        room_geom[r['colour']].append(r['poly'])
    room_geom = {c: unary_union(ps) for c, ps in room_geom.items()}
    rooms_all = unary_union([r['poly'] for r in rooms])
    zone = rooms_all.buffer(0.35, join_style='mitre').buffer(-0.35, join_style='mitre').difference(rooms_all)
    syms, swings = [], []
    keep_w = sh.info['door_w']
    for w in sorted({keep_w, 0.84}):
        sh.info['door_w'] = w
        syms += door_symbols(sh, zone, room_geom, swings)
    sh.info['door_w'] = keep_w
    # (one per door: the first symbol found at a doorway)
    x['swings'] = []
    for q in swings:
        if all(math.dist(q[:2], p[:2]) > 0.4 for p in x['swings']):
            x['swings'].append(q)
    sym_u = unary_union(syms) if syms else Polygon()
    W = unary_union([x['walls'], x['struct']]).buffer(0.04)
    air = ('loggia', 'terrace')
    pairs = defaultdict(list)
    seen = defaultdict(list)
    voids = []   # free stretches inside the plan with no room across: walled up
    facade = x['enclosure'].exterior
    for r in rooms:
        for q, g in facing(r, r['poly'].exterior.difference(W), rooms):
            if q is None:
                if g.distance(facade) > 0.8 and g.length >= 0.3:
                    voids.append(g)
                continue
            if g.length < 0.3:
                continue
            k = frozenset((id(r), id(q)))
            mid = g.interpolate(0.5, normalized=True)
            if any(src != id(r) and mid.distance(o.interpolate(0.5, normalized=True)) < 0.7 for o, src in seen[k]):
                continue  # the same opening, seen from the other room
            seen[k].append((g, id(r)))
            pairs[k].append(g)
    by_id = {id(r): r for r in rooms}
    sym_b = sym_u.buffer(0.05) if not sym_u.is_empty else sym_u
    # a door symbol on this opening: it covers most of the opening's length
    sym_hit = lambda f: (not sym_u.is_empty) and f.intersection(sym_b).length >= 0.6 * min(f.length, 0.9)
    closed, edges = [], []
    for k, segs in pairs.items():
        a, b = (by_id[i] for i in k)
        if a['common'] and b['common']:
            continue
        fa, fb = flat_of.get(id(a)), flat_of.get(id(b))
        foreign = not (a['common'] or b['common']) and fa != fb
        if foreign:
            closed += [(f, a, b) for f in segs]
            continue
        if a['kind'] in air or b['kind'] in air:
            continue
        common = a['common'] or b['common']
        score = lambda f: (sym_hit(f), -abs(f.length - 0.95) if common or f.length <= 1.4 else f.length)
        best = max(segs, key=score)
        closed += [(f, a, b) for f in segs if f is not best]
        # open plan only between the day rooms (living room, kitchen, hall); a bedroom or a bathroom
        # always has a door
        day = ('living', 'kitchen', 'hall', 'common')
        open_plan = best.length > 1.4 and a['kind'] in day and b['kind'] in day
        # (a gap narrower than a door is never a door, whatever is drawn next to it)
        # nobody walks into a bedroom through the kitchen: such a door stays only if it is the only way
        odd_pair = {a['kind'], b['kind']} == {'bedroom', 'kitchen'}
        edges.append(dict(a=a, b=b, f=best, flat=fa if fa is not None else fb,
                          strong=((sym_hit(best) and best.length >= 0.62) or open_plan) and not odd_pair))
    # weak openings (no door symbol, door-sized): walled up while the flat stays connected
    def connected(flat, live):
        nodes = [r for r in rooms if flat_of.get(id(r)) == flat and r['kind'] not in air]
        if not nodes:
            return True
        adj = defaultdict(set)
        for e in live:
            ia = 'C' if e['a']['common'] else id(e['a'])
            ib = 'C' if e['b']['common'] else id(e['b'])
            adj[ia].add(ib)
            adj[ib].add(ia)
        seen, stack = {'C'}, ['C']
        while stack:
            n = stack.pop()
            for m in adj[n] - seen:
                seen.add(m)
                stack.append(m)
        return all(id(r) in seen for r in nodes)
    kept = []
    for flat in {e['flat'] for e in edges}:
        live = [e for e in edges if e['flat'] == flat]
        if not connected(flat, live):
            continue  # (the drawing itself leaves something unreachable: change nothing)
        # least door-like first (a 3 m gap goes before a 0.8 m one)
        for e in sorted([e for e in live if not e['strong']], key=lambda e: -abs(e['f'].length - 0.85)):
            trial = [o for o in live if o is not e]
            if connected(flat, trial):
                live = trial
                closed.append((e['f'], e['a'], e['b']))
        # bathrooms, WCs and wardrobes have one door: the most door-like (drawn, about 0.8 m)
        for r in [r for r in rooms if flat_of.get(id(r)) == flat and r['kind'] in ('bath', 'wc', 'storage')]:
            mine = [e for e in live if e['a'] is r or e['b'] is r]
            mine.sort(key=lambda e: (not sym_hit(e['f']), abs(e['f'].length - 0.8)))
            for e in mine[1:]:
                trial = [o for o in live if o is not e]
                if connected(flat, trial):
                    live = trial
                    closed.append((e['f'], e['a'], e['b']))
        # a door into a bedroom, bathroom or wardrobe wider than a door (a gap in the drawing's wall):
        # one door width of it stays open, at the door symbol if there is one, the rest is walled up
        for e in live:
            day_pair = e['a']['kind'] in ('living', 'kitchen', 'hall', 'common') and e['b']['kind'] in ('living', 'kitchen', 'hall', 'common')
            f = e['f']
            if day_pair or f.length <= 1.25:
                continue
            at = f.length / 2
            if not sym_u.is_empty and f.intersection(sym_b).length > 0.3:
                hit = f.intersection(sym_b)
                c = hit.centroid if not hit.is_empty else f.interpolate(0.5, normalized=True)
                at = min(max(f.project(c), 0.45), f.length - 0.45)
            from shapely.ops import substring
            for lo, hi in ((0.0, at - 0.43), (at + 0.43, f.length)):
                if hi - lo > 0.05:
                    closed.append((substring(f, lo, hi), e['a'], e['b']))
            e['f'] = substring(f, at - 0.43, at + 0.43)
        kept += live
    dbg = os.environ.get('TIDY_DEBUG')
    if dbg:
        for f, a, b in closed:
            if any(abs(r['area'] - float(dbg)) < 0.02 for r in (a, b)):
                print('   closed', a['kind'], round(a['area'], 2), '<->', b['kind'], round(b['area'], 2), round(f.length, 2), [round(v, 2) for v in f.bounds])
        for e in edges:
            if any(abs(r['area'] - float(dbg)) < 0.02 for r in (e['a'], e['b'])):
                print('   edge', e['a']['kind'], '<->', e['b']['kind'], round(e['f'].length, 2), 'strong' if e['strong'] else 'weak', [round(v, 2) for v in e['f'].bounds])
    walls = []
    for f, a, b in closed:
        # the gap between the two rooms along this opening (not round the corner to the next one)
        g = f.buffer(0.6, cap_style='flat').intersection(zone).intersection(a['poly'].buffer(0.65)).intersection(b['poly'].buffer(0.65))
        if g.area < 0.03:
            g = f.buffer(0.1, cap_style='flat')
        walls.append(g)
    walls += [f.buffer(0.12, cap_style='flat') for f in voids]
    closed = closed + voids
    # never across a door that stays (a patch for the next opening can reach round the corner)
    keep_clear = unary_union([e['f'].buffer(0.6, cap_style='flat').intersection(zone).intersection(e['a']['poly'].buffer(0.65))
                              .intersection(e['b']['poly'].buffer(0.65)).buffer(0.02) for e in kept]) if kept else Polygon()
    walls = [w.difference(keep_clear) for w in walls]
    if walls:
        x['walls'] = snap(unary_union([x['walls']] + walls).difference(x['struct']))
    # last pass: slots left narrower than a door, or into another flat, are closed with a thin wall
    W2 = unary_union([x['walls'], x['struct']]).buffer(0.04)
    kept_lines = unary_union([e['f'].buffer(0.12) for e in kept]) if kept else Polygon()
    slots = []
    for r in rooms:
        for q, g in facing(r, r['poly'].exterior.difference(W2), rooms):
            if q is None or g.length < 0.05:
                continue
            fq, fr = flat_of.get(id(q)), flat_of.get(id(r))
            foreign = not (q['common'] or r['common']) and fq != fr
            if foreign or (g.length < 0.62 and not kept_lines.contains(g)):
                slots.append(g.buffer(0.12, cap_style='flat'))
    if slots:
        x['walls'] = snap(unary_union([x['walls']] + slots).difference(x['struct']))
    print('  doors: %d connections, %d openings walled up, %d door symbols' % (len(edges), len(closed), len(syms)))


def build(key):
    sh, x = extract(key)
    x['flats'] = group_apartments(key, x)
    tidy_doors(sh, x)
    x['windows'], x['glazing'] = openings(key, x)
    if key.startswith('A'):
        tg, door_cuts = tower_glazing(x)
        x['glazing'] = [g for g in parts(unary_union(x['glazing'] + tg))]
        # (the doors to the terraces: through the wall lines drawn there)
        x['walls'] = snap(x['walls'].difference(unary_union(tg + door_cuts).buffer(0.005)).difference(x['struct']))
        x['glazing'] = [g for g in parts(unary_union(x['glazing']).difference(unary_union(door_cuts)))]
    # fittings read from the drawing that lie across a doorway (a door swing caught in with a bath
    # or a sink): left out, the viewer furnishes the room itself
    ways = unary_union([d.buffer(0.3) for d in doorways(x)])
    keep = [fx for fx in x['fixtures'] if fx.intersection(ways).area < 0.02]
    print('  %d fittings across doorways left out' % (len(x['fixtures']) - len(keep)))
    x['fixtures'] = keep
    open_entrances(x)
    fill_slits(x)
    return sh, x


def fill_slits(x, width=0.14):
    """The slits the drawing leaves between two pieces of wall, a wall and a window, a window and
    a column (up to 14 cm; a doorway is wider): filled with wall, never into a room. Seen from
    inside they were dark lines from floor to ceiling, with the outside or the next room in them."""
    solid = unary_union([x['walls'], x['struct']] + list(x['windows']) + list(x['glazing']))
    closed = solid.buffer(width / 2, join_style='mitre').buffer(-width / 2, join_style='mitre')
    rooms = unary_union([r['poly'] for r in x['rooms']])
    slits = closed.difference(solid).difference(rooms.buffer(0.005, join_style='mitre'))
    keep = [g for g in parts(slits) if g.area > 2e-4]
    if keep:
        walls = unary_union([shapely.set_precision(x['walls'], 0)] + keep)
        # (no pinholes left inside the walls: they cannot be drawn as prisms)
        walls = unary_union([Polygon(q.exterior, [h for h in q.interiors if Polygon(h).area > 0.2]) for q in parts(walls)])
        x['walls'] = snap(walls)
    print('  %d slits between walls filled (%.2f m2)' % (len(keep), sum(g.area for g in keep)))


def open_entrances(x):
    """Every flat has a way in from the corridor. Sheet A draws some entrances as a plain opening
    in the concrete wall, with no door symbol; the strip of wall read there (between the flat and
    the corridor, door-sized, between concrete) is taken out, the viewer puts the door in."""
    common = unary_union([r['poly'] for r in x['rooms'] if r['common']])
    if common.is_empty:
        return
    solid = unary_union([x['walls'], x['struct']])
    for f in x['flats']:
        rooms = unary_union([r['poly'] for r in f['rooms'] if r['kind'] not in ('loggia', 'terrace')])
        # a way through already: free floor between a room of the flat and the corridor
        reach = rooms.buffer(0.6).intersection(common.buffer(0.6)).difference(solid)
        if any(g.intersects(rooms.buffer(0.01)) and g.intersects(common.buffer(0.01)) and min_width(g) > 0.5 for g in parts(reach)):
            continue
        cands = []
        for w in parts(x['walls']):
            if w.distance(rooms) > 0.06 or w.distance(common) > 0.06:
                continue
            L = max(min_width(w), max(math.dist(*list(w.minimum_rotated_rectangle.exterior.coords)[i:i + 2]) for i in range(2)))
            if 0.7 <= L <= 1.3 and min_width(w) <= 0.5 and w.area < 0.65:
                hall = any(r['kind'] == 'hall' and r['poly'].distance(w) < 0.06 for r in f['rooms'])
                cands.append((0 if hall else 1, abs(L - 0.95), w))
        if not cands:
            print('  flat with no way in from the corridor and no strip to open:', f.get('label'))
            continue
        _, _, w = min(cands, key=lambda c: c[:2])
        # (the walls may hold the same piece more than once: every piece within the strip goes)
        # (compared by place and size: overlays with the snapped walls lose small pieces)
        x['walls'] = snap(unary_union([g for g in parts(x['walls']) if not (g.centroid.distance(w.centroid) < 0.02 and abs(g.area - w.area) < 0.02)]))
        print('  entrance with no door symbol opened at %.1f, %.1f (%s)' % (w.centroid.x, w.centroid.y, f.get('label')))


def uncoloured_rooms(x):
    """Rooms the drawing left without their flat's colour (a bathroom drawn white on one sheet):
    the holes in the floor's outline that hold drawn sanitary ware become rooms of the flat next
    to them (a bathroom if there is a bath, else a WC)."""
    added = []
    for hole_ring in x['enclosure'].interiors:
        hole = Polygon(hole_ring)
        if not 1.0 < hole.area < 12.0:
            continue
        fits = [it for it in x.get('furniture', []) if it['type'] in ('toilet', 'bath', 'basin') and hole.contains(Point(*it['c']))]
        if not fits:
            continue
        # (less the strips of white between walls that the hole also takes in)
        poly = hole.difference(x['walls']).difference(x['struct'])
        poly = poly.buffer(-0.15, join_style='mitre').buffer(0.15, join_style='mitre').intersection(poly)
        poly = snap(max(parts(poly), key=lambda q: q.area))
        f = min(x['flats'], key=lambda f: min(r['poly'].distance(poly) for r in f['rooms']))
        kind = 'bath' if any(it['type'] == 'bath' for it in fits) else 'wc'
        r = dict(colour=f['colour'], poly=poly, common=False, fill_area=poly.area, area=poly.area, outer=0.0, fix=[],
                 width=min_width(poly), label=None, kind=kind)
        f['rooms'].append(r)
        x['rooms'].append(r)
        added.append(r)
    return added


def to_json(key, x):
    def rings(g):
        out = []
        for q in parts(g):
            pieces = no_holes(q)
            # the pieces must cover exactly the solid (no hole filled in)
            assert abs(sum(h.area for h in pieces) - q.area) < 0.01, 'hole lost while splitting'
            out += [ring(h) for h in pieces if h.area > 0.005]
        return out

    enc = x['enclosure'].simplify(0.03)
    flats = []
    for f in sorted(x['flats'], key=lambda f: (-round(f['rooms'][0]['poly'].centroid.y), f['rooms'][0]['poly'].centroid.x)):
        rooms, balconies = [], []
        for r in f['rooms']:
            en, ru, tj = ROOM_NAMES[r['kind']]
            item = dict(name=en, ru=ru, tj=tj, kind=r['kind'], area=round(r['area'], 2), poly=ring(r['poly']))
            (balconies if r['kind'] == 'terrace' else rooms).append(item)
        outline = unary_union([r['poly'].buffer(0.2, join_style='mitre') for r in f['rooms']]).buffer(-0.2, join_style='mitre')
        outline = max(parts(outline), key=lambda q: q.area)
        n, area = f.get('label', (f['rooms_count'], f['drawn_area']))
        # the furniture and sanitary ware drawn in the flat's rooms (furniture.py)
        mine = unary_union([r['poly'].buffer(0.1) for r in f['rooms']])
        furn = [it for it in x.get('furniture', []) if mine.contains(Point(*furniture.point_of(it)))]
        flats.append(dict(colour='#%02x%02x%02x' % tuple(int(v * 255) for v in f['colour']), rooms_count=n,
                          label_rooms=n, area=round(area, 2), outline=ring(outline), rooms=rooms, balconies=balconies,
                          furniture=furn))
    common = [ring(r['poly']) for r in x['rooms'] if r['common']]
    return dict(title=SHEET_INFO[key]['title'], slab=ring(enc), enclosure=ring(enc), walls=rings(x['walls']),
                struct=rings(x['struct']), windows=[ring(w) for w in x['windows']], glazing=[ring(g) for g in x['glazing']],
                common=common, apartments=flats, lifts=x.get('lifts', []),
                swings=[[p[0], p[1], p[2], p[3]] for p in x.get('swings', [])])


def keep_order(new, old):
    """The flats in the order of the previous export: the site numbers the flats of a floor in
    this order, so a change to the extraction must not renumber them."""
    if not old or len(old.get('apartments', [])) != len(new['apartments']):
        return new
    nc = [Polygon(a['outline']).centroid for a in new['apartments']]
    order = []
    for a in old['apartments']:
        o = Polygon(a['outline']).centroid
        free = [j for j in range(len(nc)) if j not in order]
        j = min(free, key=lambda j: nc[j].distance(o))
        if nc[j].distance(o) > 2.0:
            return new   # the plan has changed: numbered afresh
        order.append(j)
    if order != sorted(order):
        print('  flats kept in the order of the previous export')
    new['apartments'] = [new['apartments'][j] for j in order]
    return new


def draw_debug(key, x, scale=40):
    from PIL import Image, ImageDraw, ImageFont
    x0, y0, x1, y1 = x['enclosure'].buffer(1.5).bounds
    im = Image.new('RGB', (int((x1 - x0) * scale), int((y1 - y0) * scale)), 'white')
    g = ImageDraw.Draw(im)
    T = lambda p: ((p[0] - x0) * scale, (y1 - p[1]) * scale)
    KC = {'living': (255, 215, 140), 'bedroom': (170, 200, 255), 'kitchen': (255, 170, 170), 'hall': (225, 225, 200),
          'bath': (140, 230, 230), 'wc': (120, 200, 210), 'storage': (210, 180, 230), 'loggia': (190, 240, 170),
          'terrace': (150, 225, 120), 'common': (235, 235, 235)}
    poly = lambda q, **kw: g.polygon([T(p) for p in q.exterior.coords], **kw)
    for r in x['rooms']:
        poly(r['poly'], fill=KC[r['kind']], outline=(150, 150, 150))
    for q in parts(x['walls']):
        for h in no_holes(q):
            poly(h, fill=(30, 30, 30))
    for q in parts(x['struct']):
        for h in no_holes(q):
            poly(h, fill=(40, 60, 200))
    for w in x.get('windows', []):
        poly(w, fill=(0, 200, 255))
    for w in x.get('glazing', []):
        poly(w, fill=(0, 110, 255))
    for f in x['fixtures']:
        poly(f, outline=(150, 100, 30))
    for d in x['doors_balc']:
        g.line([T(p) for p in d.coords], fill=(255, 100, 0), width=2)
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 13)
        big = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 17)
    except OSError:
        font = big = None
    for f in x.get('flats', []):
        o = unary_union([r['poly'].buffer(0.2) for r in f['rooms']]).buffer(-0.1)
        for q in parts(o):
            g.line([T(p) for p in q.exterior.coords], fill=(255, 0, 120), width=3)
        c = max(f['rooms'], key=lambda r: r['area'])['poly'].representative_point()
        n, a = f.get('label', ('?', f['drawn_area']))
        g.text(T((c.x, c.y + 0.9)), f'{n}к {a:.2f}', fill=(200, 0, 90), font=big, anchor='mm')
    for r in x['rooms']:
        c = r['poly'].representative_point()
        g.text(T((c.x, c.y)), f"{ROOM_NAMES.get(r['kind'], ('', r['kind']))[1] if r['kind'] != 'common' else ''} {r['area']:.1f}",
               fill=(0, 0, 0), font=font, anchor='mm')
    im.save(os.path.join(ROOT, 'build', 'plans', f'{key}.png'))


def main():
    os.makedirs(os.path.join(ROOT, 'build', 'plans'), exist_ok=True)
    keys = sys.argv[1:] or list(SHEET_INFO)
    out = {}
    for key in keys:
        sh, x = build(key)
        x['furniture'], x['lifts'] = furniture.extract(sh, x)
        for r in uncoloured_rooms(x):
            print('  a room drawn without its colour: %s %.2f m2 at %.1f, %.1f' % (r['kind'], r['area'], r['poly'].centroid.x, r['poly'].centroid.y))
        print(key, 'rooms', len(x['rooms']), 'flats', len(x['flats']), '(labels %d)' % len(LABELS[key]),
              'windows', len(x['windows']), 'glazing', len(x['glazing']), 'walls %.0f m2' % x['walls'].area)
        for f in sorted(x['flats'], key=lambda f: f['drawn_area']):
            kinds = sorted(r['kind'] for r in f['rooms'])
            print('   drawn %6.1f label %-12s rooms %d  %s' % (f['drawn_area'], f.get('label'), f['rooms_count'], ' '.join(kinds)))
        draw_debug(key, x)
        out[key] = to_json(key, x)
    dst = os.path.join(ROOT, 'blender', 'ab', 'plans.json')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    old = json.load(open(dst)) if os.path.exists(dst) else {}
    for key in out:
        out[key] = keep_order(out[key], old.get(key))
    old.update(out)
    json.dump(old, open(dst, 'w'), separators=(',', ':'), ensure_ascii=False)
    print('->', dst)


if __name__ == '__main__':
    main()
