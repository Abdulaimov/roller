"""Floor plans of Regnum Plaza (blocks А, Б, В) read off the sales book -> blender/rp/plans.json.

    tools/ab/py tools/rp/extract.py [PLAN ...]        # all plans, or e.g. A_typ V_25
    tools/ab/py tools/rp/extract.py --check            # + overlay pictures build/rp/plans/*.png
    tools/ab/py tools/rp/extract.py --furniture        # the furniture read again, the plans kept

How the sheets are drawn (vector, colours exact):
  brown strokes        partitions                     magenta / red outlines   concrete walls, pylons
  blue / navy lines    outer walls (two lines)         bright blue (0,60,252)   window glass in a wall
  cyan                 balcony glazing / glass rail    dark red short strokes   door leaves (open ~45°)
  black thin lines     furniture, sanitary ware        grey                     facade pilasters, lift X
  pastel fills         one colour per flat (white too) lavender + grid          balconies
The text is real text: every room has its name (Tajik) and its area, every flat a box «N-Хонага S m²»
in the flat's colour.

Method: the sheet is rendered at 600 dpi (8 px per 10 cm); the wall colours make a barrier; the room
labels seed a watershed over the free floor (cost: closeness to the walls), so the rooms meet in the
narrowest place between them - the doorways; and a label floods only its own fill colour (a
balcony's lavender, the flat's colour), so no room runs through a doorway into a room of another
colour. Each room is then opened by 30 cm (the doorway
stubs go), traced and squared up. Walls are the barrier itself; windows the bright blue glass, taken
across the whole wall; door swings from the leaves (which side the door opens to). Rooms of one
colour that reach one another through doorways are one flat, matched to the flat box of the colour.
Everything is in plan metres of the block (sheet.py: x right, y up the sheet, 0 at the middle of the
block's axes). Nothing is mirrored: every flat keeps its own drawing.
"""
import json
import math
import os
import re
import sys

import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage.segmentation import watershed
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.prepared import prep

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet as SH  # noqa: E402

ROOT = SH.ROOT
OUT = os.path.join(ROOT, 'blender', 'rp', 'plans.json')
DBG = os.path.join(ROOT, 'build', 'rp', 'plans')

# plan key -> (sheet, block, title)
PLANS = {
    'A_typ': ('typ', 'A', 'Блок А: этажи 3–22'),
    'A_23': ('f23', 'A', 'Блок А: 23 этаж'),
    'B_3': ('f3', 'B', 'Блок Б: 3 этаж'),
    'B_typ': ('typ', 'B', 'Блок Б: этажи 4–18'),
    'B_19': ('f19', 'B', 'Блок Б: 19 этаж'),
    'V_typ': ('typ', 'V', 'Блок В: этажи 3–22'),
    'V_23': ('f23', 'V', 'Блок В: этажи 23–24'),
    'V_25': ('f25', 'V', 'Блок В: 25 этаж'),
}
# how far each block's drawing goes past its outer axes (m): left, right, bottom, top. Blocks Б and
# А, В and Б stand 1.4 m apart on the sheets: each takes half of the gap.
CLIP = {'A': (3.6, 3.6, 3.6, 0.7), 'B': (0.7, 4.2, 0.7, 4.2), 'V': (3.6, 0.7, 3.6, 3.6)}

COL = {
    'brown': (144, 36, 0), 'red': (252, 0, 0), 'blue': (0, 0, 252), 'navy': (0, 24, 120),
    'glass': (0, 60, 252), 'cyan': (0, 252, 252), 'magenta': (252, 0, 252), 'jamb': (72, 84, 84),
    'blue2': (24, 24, 252), 'blue3': (0, 120, 252), 'leaf': (180, 0, 0), 'black': (0, 0, 0),
    'grey': (144, 144, 144), 'green': (108, 192, 24), 'orange': (252, 120, 0), 'text': (204, 0, 0),
}
BARRIER = ('brown', 'red', 'blue', 'navy', 'glass', 'cyan', 'magenta', 'jamb', 'blue2', 'blue3')
STRUCT = ('red', 'magenta', 'navy')

ROOM_KINDS = [  # (regex on the Tajik name, kind)
    (r'^мехмонхона ба толори', 'living'), (r'^мехмонхона', 'living'), (r'^толори', 'living'), (r'^хонаи умум', 'living'),
    (r'^хонаи хоб', 'bedroom'), (r'^ошхона', 'kitchen'), (r'^(дахлез|долон|холл?а?)$', 'hall'),
    (r'^с/у$', 'bath'), (r'^ваннахона', 'bath'), (r'^гардероб', 'storage'), (r'^анбор', 'storage'),
    (r'^балкон', 'loggia'), (r'^айвони кушода', 'terrace'), (r'^айвон', 'loggia'),
]
NAMES = {  # kind -> (en, ru, tj)
    'living': ('Living room', 'Гостиная', 'Меҳмонхона'),
    'bedroom': ('Bedroom', 'Спальня', 'Хонаи хоб'),
    'kitchen': ('Kitchen', 'Кухня', 'Ошхона'),
    'hall': ('Hall', 'Холл', 'Даҳлез'),
    'bath': ('Bathroom', 'Санузел', 'Ҳоҷатхона'),
    'wc': ('WC', 'Туалет', 'Ҳоҷатхона'),
    'storage': ('Wardrobe', 'Гардероб', 'Гардероб'),
    'loggia': ('Balcony', 'Балкон', 'Балкон'),
    'terrace': ('Terrace', 'Терраса', 'Айвони кушода'),
}
COMMON = re.compile(r'^(холл|рохрав|долони лифт|тамбур|лобби|зинапоя)', re.I)
# links the door test gets wrong (two flats of one colour side by side): pairs of room areas
NO_LINK = {'V_25': [(3.59, 41.1)], 'B_3': [(13.31, 9.63)]}   # (B_3: two white flats, kitchens back to back)
# flats the colours can't tell apart (floor 25 of В: the five-room flat's rooms are close to the
# colour of the flat beside it): box area -> the areas of its rooms, nearest the box first
# (190.53: its rooms add up to it exactly - the 6.48 by the stairs is no part of it, its entrance
# hall 8.04 and bathroom 4.65 are; 195.15: the balcony 5.40 opens from two of its bedrooms, the
# 3.59 from its hall - 0.30 over the box)
FORCE = {'V_25': {195.15: [41.1, 21.45, 19.21, 17.67, 17.34, 16.94, 15.68, 5.47, 5.4, 4.82, 3.59, 20.3, 6.48],
                  190.53: [23.99, 21.71, 21.45, 20.5, 20.3, 19.97, 17.67, 16.94, 8.93, 8.04, 4.65, 4.58, 1.8],
                  118.03: [32.79, 21.68, 21.51, 14.59, 7.87, 6.58, 5.47, 3.86, 3.58],
                  61.33: [19.78, 19.25, 10.81, 7.18, 4.31]}}
BALCONY = (228, 228, 252)   # the balconies' fill (with a tile grid)
SMALL_LOGGIA = 3.4   # m2: an unnamed small room on the facade with an AC box: the AC loggia


def tj(s):
    return s.replace('Х', 'Ҳ', 0)


# --------------------------------------------------------------------------- raster

class Raster:
    def __init__(self, pg, fr, clip):
        self.fr, self.pg = fr, pg
        cl, cr, cb, ct = clip
        a = SH.AXES[fr.key]
        X0, X1 = -fr.cxm - cl, a['xm'][-1] - fr.cxm + cr
        Y0, Y1 = -fr.cym - cb, a['ym'][-1] - fr.cym + ct
        x0, y1 = fr.to_sheet(X0, Y0)
        x1, y0 = fr.to_sheet(X1, Y1)
        self.rect = SH.pymupdf.Rect(x0, y0, x1, y1)
        pix = pg.get_pixmap(dpi=SH.DPI, clip=self.rect, alpha=False)
        self.img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3)
        self.H, self.W = pix.h, pix.w
        self.k = 72 / SH.DPI                 # pt per px
        self.ppm = fr.s / self.k             # px per metre
        self._cls = {}

    def cls(self, name, tol=34):
        if name not in self._cls:
            c = np.array(COL[name], np.int16)
            self._cls[name] = np.abs(self.img.astype(np.int16) - c).max(axis=2) < tol
        return self._cls[name]

    def any(self, names):
        m = np.zeros((self.H, self.W), bool)
        for n in names:
            m |= self.cls(n)
        if 'brown' in names:  # partitions: the brown hue at any darkness (some are drawn darker)
            q = self.img.astype(np.int16)
            r, g, b = q[..., 0], q[..., 1], q[..., 2]
            m |= (r >= 24) & (b <= 12) & (g * 100 >= r * 15) & (g * 100 <= r * 35)
        return m

    # px <-> plan
    def plan(self, px, py):
        return self.fr.to_plan(self.rect.x0 + (px + 0.5) * self.k, self.rect.y0 + (py + 0.5) * self.k)

    def px(self, X, Y):
        x, y = self.fr.to_sheet(X, Y)
        return ((x - self.rect.x0) / self.k - 0.5, (y - self.rect.y0) / self.k - 0.5)

    def sheet_px(self, x, y):
        return ((x - self.rect.x0) / self.k, (y - self.rect.y0) / self.k)

    def poly(self, contour):
        return [self.plan(float(p[0]), float(p[1])) for p in contour]


def disk(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def sq(n):
    return np.ones((n, n), np.uint8)


# --------------------------------------------------------------------------- text

def read_text(pg, rect):
    """room labels: [{name, area, x, y (sheet pt of the area figure)}], flat boxes, appliance tags"""
    lines = []
    for b in pg.get_text('dict', clip=rect)['blocks']:
        for line in b.get('lines', []):
            t = ' '.join(s['text'] for s in line['spans']).strip()
            if not t:
                continue
            x0, y0, x1, y1 = line['bbox']
            s = line['spans'][0]
            lines.append(dict(t=t, x=(x0 + x1) / 2, y=(y0 + y1) / 2, bbox=line['bbox'], size=s['size'], color=s['color'],
                              dir=line['dir']))
    rooms, flats, tags = [], [], []
    names = [ln for ln in lines if re.search(r'[А-Яа-яҲҳӮӯҶҷ]{2,}', ln['t']) and 3.0 < ln['size'] < 4.5
             and not re.search(r'хонага', ln['t'], re.I)]
    for ln in lines:
        m = re.fullmatch(r'(\d+)[.,](\d\d)', ln['t'])
        if m and 3.0 < ln['size'] < 6.5:
            area = float(f'{m.group(1)}.{m.group(2)}')
            # the name above it (within 7 pt), the nearest
            cands = [n for n in names if 0 < ln['y'] - n['y'] < 8.5 and abs(n['x'] - ln['x']) < 14]
            nm = min(cands, key=lambda n: (ln['y'] - n['y']) + abs(n['x'] - ln['x']) * 0.3)['t'] if cands else ''
            rooms.append(dict(name=nm, area=area, x=ln['x'], y=ln['y'], bbox=ln['bbox']))
        m = re.fullmatch(r'(\d)-\s*Хонага', ln['t'], re.I)
        if m:
            flats.append(dict(rooms=int(m.group(1)), x=ln['x'], y=ln['y'], bbox=ln['bbox']))
        if ln['t'] in ('ПЭ', 'Х', 'Ст.М.') and ln['size'] < 2.5:
            tags.append(dict(t=ln['t'], x=ln['x'], y=ln['y']))
    # flat areas: the line under each «N-Хонага»
    for f in flats:
        below = [ln for ln in lines if 0 < ln['y'] - f['y'] < 7 and abs(ln['x'] - f['x']) < 10 and re.search(r'\d', ln['t'])]
        if below:
            b = min(below, key=lambda ln: ln['y'] - f['y'])
            m = re.search(r'(\d+)[.,](\d+)', b['t'])
            if m:
                f['area'] = float(f'{m.group(1)}.{m.group(2)}')
            m2 = re.search(r'\((\d+)[.,](\d+)\)', b['t'])
            if m2:
                f['terrace'] = float(f'{m2.group(1)}.{m2.group(2)}')
        f['bbox'] = (min(f['bbox'][0], b['bbox'][0]) if below else f['bbox'][0], f['bbox'][1],
                     max(f['bbox'][2], b['bbox'][2]) if below else f['bbox'][2], b['bbox'][3] if below else f['bbox'][3])
    return rooms, flats, tags, lines


def kind_of(name):
    n = name.lower().replace('ҳ', 'х').replace('ӯ', 'у').replace('ӣ', 'и').strip()
    for rx, k in ROOM_KINDS:
        if re.search(rx, n):
            return k
    return None


# --------------------------------------------------------------------------- geometry

def trace(mask, R, eps_m=0.025):
    """outer outline of a mask as a plan polygon, squared up (edges within 6° of the axes made
    exactly straight)"""
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs:
        return None
    c = max(cs, key=cv2.contourArea)
    # (simplified keeping its topology: cv2.approxPolyDP could cross the outline over itself at a
    # narrow place - a kitchen niche, a strip of worktop - and the repair then dropped that part)
    if len(c) < 3:
        return None
    g = Polygon(c[:, 0, :].astype(float)).buffer(0)
    if g.is_empty:
        return None
    g = max(getattr(g, 'geoms', [g]), key=lambda q: q.area).simplify(eps_m * R.ppm, preserve_topology=True)
    c = np.array(g.exterior.coords[:-1], float)
    if len(c) < 3:
        return None
    pts = square(square(c), chamfer=0.3 * R.ppm)
    poly = [R.plan(x, y) for x, y in pts]
    p = Polygon(poly).buffer(0)
    if p.is_empty:
        return None
    if p.geom_type != 'Polygon':
        p = max(p.geoms, key=lambda g: g.area)
    # (slits a few millimetres wide from a wall into the room - a stroke of wall colour in a
    # drawing - closed; square corners stay square)
    q = p.buffer(0.03, join_style=2).buffer(-0.03, join_style=2)
    if q.geom_type == 'Polygon' and not q.is_empty:
        p = q
    p = p.simplify(0.004)
    q = list(p.exterior.coords)[:-1]
    if not Polygon(q).exterior.is_ccw:
        q = q[::-1]
    return [[round(x, 3), round(y, 3)] for x, y in q]


def square(c, chamfer=None):
    """make near-axis edges exactly axis-aligned: snap runs of points to shared x / y; short
    diagonal edges between two square edges (the corners the opening rounded off) made corners"""
    pts = [list(p) for p in c]
    if chamfer:
        for _ in range(3):
            n = len(pts)
            if n < 5:
                break
            out, i, changed = [], 0, False
            def kind(a, b):
                ang = abs(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))) % 180
                return 'h' if ang < 8 or ang > 172 else 'v' if abs(ang - 90) < 8 else 'd'
            keep = [True] * n
            newp = {}
            for i in range(n):
                p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
                if kind(p1, p2) == 'd' and math.dist(p1, p2) < chamfer and {kind(p0, p1), kind(p2, p3)} == {'h', 'v'} \
                        and keep[i] and keep[(i + 1) % n]:
                    if kind(p0, p1) == 'h':
                        c_ = [p3[0] if kind(p2, p3) == 'v' else p2[0], p0[1]]
                        c_ = [p2[0], p1[1]]
                    else:
                        c_ = [p1[0], p2[1]]
                    newp[i] = c_
                    keep[(i + 1) % n] = False
                    changed = True
            pts = [newp.get(i, pts[i]) for i in range(n) if keep[i]]
            if not changed:
                break
    n = len(pts)
    for _ in range(2):
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy)
            if L < 1e-6:
                continue
            ang = abs(math.degrees(math.atan2(dy, dx))) % 180
            if ang < 6 or ang > 174:
                y = (a[1] + b[1]) / 2
                a[1] = b[1] = y
            elif abs(ang - 90) < 6:
                x = (a[0] + b[0]) / 2
                a[0] = b[0] = x
    return pts


def mask_poly(poly, R, shape):
    m = np.zeros(shape, np.uint8)
    pts = np.array([R.px(x, y) for x, y in poly], np.int32)
    cv2.fillPoly(m, [pts], 1)
    return m.astype(bool)


def comps(mask, min_px=1):
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    return [(i, st[i], cen[i]) for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= min_px], lab


# --------------------------------------------------------------------------- one plan

def extract(key, debug=False):
    sheet, block, title = PLANS[key]
    d = SH.doc()
    pg = d[SH.PAGES[sheet]]
    fr, res = SH.fit(pg, block)
    R = Raster(pg, fr, CLIP[block])
    ppm = R.ppm
    H, W = R.H, R.W
    text_rooms, _, tags, lines = read_text(pg, R.rect)
    # the flat boxes stand outside the drawing: read them further out, keep this block's
    big = SH.pymupdf.Rect(R.rect.x0 - 14 * fr.s, R.rect.y0 - 14 * fr.s, R.rect.x1 + 14 * fr.s, R.rect.y1 + 14 * fr.s)
    _, text_flats, _, _ = read_text(pg, big)
    others = []
    for k2 in ('A', 'B', 'V'):
        try:
            others.append((k2, SH.fit(pg, k2)[0]))
        except Exception:
            pass
    def owner(f):
        best = None
        for k2, f2 in others:
            X, Y = f2.to_plan(f['x'], f['y'])
            a2 = SH.AXES[k2]
            dx = max(abs(X) - (a2['xm'][-1] - a2['xm'][0]) / 2, 0)
            dy = max(abs(Y) - (a2['ym'][-1] - a2['ym'][0]) / 2, 0)
            dd = math.hypot(dx, dy)
            if best is None or dd < best[0]:
                best = (dd, k2)
        return best[1]
    text_flats = [f for f in text_flats if owner(f) == block]

    barrier = R.any(BARRIER)
    barrier = cv2.morphologyEx(barrier.astype(np.uint8), cv2.MORPH_CLOSE, sq(3)).astype(bool)
    # (the marks a drawn door leaf carries - the hinge dot, the cap at its tip - are no wall: small
    # spots of wall colour on or beside a leaf, standing in the doorway or the room)
    leaf_near = cv2.dilate(R.cls('leaf').astype(np.uint8), disk(max(2, int(0.08 * ppm)))).astype(bool)
    cs_b, lab_b = comps(barrier & leaf_near, 1)
    for i_b, st_b, _ in cs_b:
        if st_b[cv2.CC_STAT_AREA] < 0.03 * ppm * ppm and max(st_b[cv2.CC_STAT_WIDTH], st_b[cv2.CC_STAT_HEIGHT]) < 0.3 * ppm:
            part = lab_b == i_b
            # (only where the spot is not the end of a wall: little of it touches wall away from the leaf)
            ring = cv2.dilate(part.astype(np.uint8), sq(5)).astype(bool) & ~part & barrier & ~leaf_near
            if ring.sum() < 0.25 * part.sum():
                barrier &= ~part
    # (the hinge dots: a dark ring of the jamb's or the outer wall's colour round the leaf's end,
    # stuck to the end of the wall and reaching into the doorway)
    ring_c = barrier & leaf_near & (R.cls('jamb') | R.cls('navy'))
    cs_b, lab_b = comps(ring_c, 1)
    for i_b, st_b, _ in cs_b:
        if st_b[cv2.CC_STAT_AREA] < 0.012 * ppm * ppm:
            barrier &= ~(lab_b == i_b)

    # ---- the building: everything inked except thin lines (axes, dimensions), with its holes
    white = (R.img.min(axis=2) > 238)
    ink = ~white & ~R.cls('green', 40) & ~R.cls('grey', 30)
    ink = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_OPEN, sq(5))
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, sq(9))
    ink = ndi.binary_fill_holes(ink)
    # keep the parts round the block's own axes
    axes_box = mask_poly([(-fr.cxm, -fr.cym), (fr.cxm, -fr.cym), (fr.cxm, fr.cym), (-fr.cxm, fr.cym)], R, (H, W))
    cs, lab = comps(ink, 50)
    keep = np.zeros((H, W), bool)
    for i, st, _ in cs:
        part = lab == i
        if (part & axes_box).sum() > 0.02 * part.sum():
            keep |= part
    # the flat boxes and the dimension texts outside: not building
    for f in text_flats:
        x0, y0 = R.sheet_px(f['bbox'][0] - 4, f['bbox'][1] - 2)
        x1, y1 = R.sheet_px(f['bbox'][2] + 4, f['bbox'][3] + 2)
        keep[max(0, int(y0)):int(y1) + 1, max(0, int(x0)):int(x1) + 1] = False
    building = keep
    free = building & ~barrier
    # ---- the doors: the sheet closes every room by walls and doors. Each drawn doorway is shut
    # by a line from the leaf's hinge across the gap for the watershed, so that no room's label runs
    # through a door into the next room of the same colour (a bathroom into the hall, a bedroom
    # into the corridor): the rooms come out as the walls and doors draw them
    swings = door_swings(R, R.cls('leaf') & building, barrier, None, vector_leaves(pg, fr, R.rect))
    shut = np.zeros((H, W), np.uint8)
    for q in swings:
        h, m = np.array(q[4:6], float), np.array(q[:2], float)
        L = 2 * np.linalg.norm(m - h)
        if L < 0.4:
            continue
        u = (m - h) / (L / 2)
        a, b = R.px(*(h - u * 0.06)), R.px(*(h + u * (L + 0.06)))
        cv2.line(shut, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), 1, max(2, int(0.025 * ppm)))
    free_ws = free & ~shut.astype(bool)

    # ---- seeds: one per room label (the area figure)
    rooms_txt = []
    for t in text_rooms:
        cx, cy = R.sheet_px(t['x'], t['y'])
        if not (0 <= cx < W and 0 <= cy < H) or not building[int(cy), int(cx)]:
            continue
        nm = t['name']
        t = dict(t, px=(cx, cy), kind=kind_of(nm), common=bool(COMMON.match(nm.lower())))
        rooms_txt.append(t)
    # the stairs: no label, an orange handrail up the middle
    cs_o, lab_o = comps(R.cls('orange', 40) & building, int(0.02 * ppm * ppm))
    for i_o, st_o, cen_o in cs_o:
        X, Y = R.plan(*cen_o)
        rooms_txt.append(dict(name='Зинапоя', area=0.0, x=0, y=0, px=(cen_o[0], cen_o[1]), kind=None, common=True, stair=True))
    markers = np.zeros((H, W), np.int32)
    for i, t in enumerate(rooms_txt, 1):
        cx, cy = t['px']
        r = int(0.12 * ppm)
        sub = np.zeros((H, W), np.uint8)
        cv2.circle(sub, (int(cx), int(cy)), r, 1, -1)
        sub = sub.astype(bool) & free
        if not sub.any():  # the figure sits on a line: the nearest free pixel
            ys, xs = np.nonzero(free[max(0, int(cy) - 40):int(cy) + 40, max(0, int(cx) - 40):int(cx) + 40])
            if len(xs):
                j = np.argmin((xs - 40) ** 2 + (ys - 40) ** 2)
                sub[max(0, int(cy) - 40) + ys[j], max(0, int(cx) - 40) + xs[j]] = True
        markers[sub] = i
    markers[~free_ws] = 0
    dist = cv2.distanceTransform(free_ws.astype(np.uint8), cv2.DIST_L2, 5)
    cost = dist.max() - dist
    ws = colour_watershed(R, cost, markers, free_ws, rooms_txt)

    # ---- rooms
    k_open = disk(max(1, int(0.15 * ppm)))
    rooms = []
    room_mask = np.zeros((H, W), np.int32)
    for i, t in enumerate(rooms_txt, 1):
        m = (ws == i)
        if m.sum() < 0.3 * ppm * ppm:
            continue
        m = ndi.binary_fill_holes(m)
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, k_open).astype(bool)
        # the part with the label
        cs2, lab2 = comps(m, 10)
        if not cs2:
            continue
        cx, cy = t['px']
        best = max(cs2, key=lambda c: (lab2[int(cy), int(cx)] == c[0], c[1][cv2.CC_STAT_AREA]))
        m = lab2 == best[0]
        poly = trace(m, R)
        if not poly:
            continue
        # (the opening can cut a room in two at a narrow place - a strip of worktop along a wall
        # behind its front line, a niche: big parts close to the room's main part are joined back)
        parts = [Polygon(poly)]
        for c in cs2:
            if c[0] == best[0] or c[1][cv2.CC_STAT_AREA] < 0.4 * ppm * ppm:
                continue
            q = trace(lab2 == c[0], R)
            if q and Polygon(q).distance(parts[0]) < 0.35:
                parts.append(Polygon(q))
                m = m | (lab2 == c[0])
        if len(parts) > 1:
            g = unary_union(parts).buffer(0.18, join_style=2).buffer(-0.18, join_style=2)
            if g.geom_type == 'Polygon':
                ring = list(g.simplify(0.004).exterior.coords)[:-1]
                if not Polygon(ring).exterior.is_ccw:
                    ring = ring[::-1]
                poly = [[round(x, 3), round(y, 3)] for x, y in ring]
        area = Polygon(poly).area
        room_mask[m] = i
        sx, sy = R.plan(*t['px'])
        col = fill_colour(R, m)
        if t['common'] and not t.get('stair') and re.match(r'^холл', t['name'].lower()) and max(col) - min(col) >= 8:
            t = dict(t, common=False, kind='hall')   # a hall inside a flat (in the flat's colour)
        rooms.append(dict(i=i, name=t['name'], kind=t['kind'], common=t['common'], stair=t.get('stair', False), area=t['area'] or round(area, 2), poly=poly,
                          measured=round(area, 2), at=(round(sx, 3), round(sy, 3)), colour=col))

    # ---- walls: the barrier, plus the free slivers no room took that touch no room twice
    taken = room_mask > 0
    left = free & ~taken
    cs3, lab3 = comps(left, 1)
    shafts = []
    wall = barrier & building
    near = cv2.dilate(taken.astype(np.uint8), disk(int(0.12 * ppm))).astype(bool)
    for i, st, cen in cs3:
        part = lab3 == i
        w_, h_ = st[cv2.CC_STAT_WIDTH] / ppm, st[cv2.CC_STAT_HEIGHT] / ppm
        if min(w_, h_) > 0.9 and st[cv2.CC_STAT_AREA] / ppm ** 2 > 1.2:
            shafts.append(part)          # a shaft or a void: left empty
        elif (part & near).sum() < 0.25 * part.sum():
            wall |= part                 # inside a wall (between the two lines of an outer wall)
    wall = cv2.morphologyEx(wall.astype(np.uint8), cv2.MORPH_CLOSE, sq(3)).astype(bool) & ~taken

    # windows: the glass in the walls, taken across the wall
    glass = R.cls('glass') & building
    if block == 'B':
        # block Б draws its windows as blue lines in the outer wall between the concrete piers
        band = cv2.dilate((~building).astype(np.uint8), disk(int(0.55 * ppm))).astype(bool) & building
        q = R.img.astype(np.int16)
        blueish = (q[..., 2] > 180) & (q[..., 0] < 110) & (q[..., 1] < 150)
        glass |= blueish & band & ~R.any(('magenta', 'navy', 'red'))
        glass = cv2.morphologyEx(glass.astype(np.uint8), cv2.MORPH_CLOSE, sq(9)).astype(bool)
    win_polys, win_mask = windows(R, glass, wall, taken)
    # concrete
    struct_m = R.any(STRUCT) & wall
    struct_m = ndi.binary_fill_holes(cv2.morphologyEx(struct_m.astype(np.uint8), cv2.MORPH_CLOSE, sq(5)))
    struct_m &= wall
    wall_rest = wall & ~struct_m & ~win_mask
    # balcony parapets: the lines between a balcony and the open air (railings, not walls)
    outdoor = np.isin(room_mask, [r['i'] for r in rooms if r['kind'] in ('loggia', 'terrace') or
                                  max(abs(a - b) for a, b in zip(r['colour'], BALCONY)) <= 10])
    reach = disk(int(0.28 * ppm))
    para = wall_rest & cv2.dilate(outdoor.astype(np.uint8), reach).astype(bool) & cv2.dilate((~building).astype(np.uint8), reach).astype(bool)
    para = cv2.morphologyEx(para.astype(np.uint8), cv2.MORPH_OPEN, sq(3)).astype(bool)
    wall_rest &= ~para
    parapets = polys_of(para, R, 0.012)
    walls = polys_of(wall_rest, R, 0.012)
    struct = polys_of(struct_m & ~win_mask, R, 0.03)
    cyan = R.cls('cyan') & building
    glazing = polys_of(cv2.dilate(cyan.astype(np.uint8), sq(3)).astype(bool) & ~taken, R, 0.01)

    # ---- rooms and walls from the sheet's vector fills (the raster above is the fallback)
    out_ring = trace(cv2.morphologyEx(building.astype(np.uint8), cv2.MORPH_CLOSE, sq(15)).astype(bool), R, 0.04)
    vec = vector_plan(pg, fr, R, rooms, struct, win_polys, parapets, glazing, swings, out_ring, barrier, wall | struct_m, struct_m)
    doorways = []
    if vec:
        walls, struct, doorways = vec
    else:
        square_doorways(rooms, walls, struct, swings)

    # ---- lifts: the shafts with the grey cross
    lifts = lift_crosses(pg, R, rooms)

    # ---- facade pilasters: the grey outlines drawn against the outside of the walls
    pil = facade_pilasters(R, building)

    # ---- the outline of the floor
    out = trace(cv2.morphologyEx(building.astype(np.uint8), cv2.MORPH_CLOSE, sq(15)).astype(bool), R, 0.04)

    plan = dict(key=key, title=title, sheet=sheet, block=block, slab=out, enclosure=out, walls=walls, struct=struct, pilasters=pil, parapets=parapets,
                windows=win_polys, glazing=glazing, swings=swings, doorways=doorways, lifts=lifts, tags=[
                    dict(t=tg['t'], at=[round(v, 3) for v in R.fr.to_plan(tg['x'], tg['y'])]) for tg in tags],
                rooms_raw=rooms, flats_raw=[dict(f, at=[round(v, 3) for v in fr.to_plan(f['x'], f['y'])],
                                                  colour=box_colour(R, f)) for f in text_flats])
    group_flats(plan, R)
    open_closed_rooms(pg, fr, plan)
    import furniture as FU
    FU.read(pg, fr, plan, R.rect)
    # (an unnamed room behind a sliding door with no sanitary ware drawn in it - block В's П of
    # shelves - is a walk-in wardrobe, not a bathroom)
    for apt in plan['apartments']:
        for r in apt['rooms']:
            if r.pop('slide', False) and r['kind'] == 'bath' and not r['label']:
                g = Polygon(r['poly']).buffer(0.05)
                wet = any(it['type'] in ('toilet', 'basin', 'bath', 'shower') and g.contains(Point(*(it.get('c') or it['boxes'][0])[:2]))
                          for it in apt['furniture'])
                if not wet:
                    r['kind'] = 'storage'
                    r['name'], r['ru'], r['tj'] = NAMES['storage']
    if debug:
        draw_debug(key, plan, R, ws)
    return plan


def seed_colour(R, px, r):
    """the fill round a label (the most common pastel colour within r px; text, lines and white
    left out), or None in a white room (where the commonest colour is only the edges of the red
    figures or of the axis lines: under a quarter of the pixels)"""
    cx, cy = int(px[0]), int(px[1])
    sub = R.img[max(0, cy - r):cy + r, max(0, cx - r):cx + r].reshape(-1, 3)
    n = len(sub)
    sub = sub[(sub.min(axis=1) >= 90) & (sub.max(axis=1) >= 200) & (sub.min(axis=1) < 246)]
    if len(sub) < 30:
        return None
    q = (sub // 4).astype(np.int32)
    keyv = q[:, 0] * 10000 + q[:, 1] * 100 + q[:, 2]
    vals, cnt = np.unique(keyv, return_counts=True)
    if cnt.max() < 0.25 * n:
        return None
    v = vals[np.argmax(cnt)]
    return (int(v // 10000) * 4 + 2, int(v // 100 % 100) * 4 + 2, int(v % 100) * 4 + 2)


def colour_watershed(R, cost, markers, free, rooms_txt, tol=8):
    """The watershed, kept to each room's fill colour: the sheets fill every flat in its own colour
    and the balconies in lavender, so a label floods only the pixels of its own colour (and the
    lines, text and white openings, which any room may take). Without this a balcony's label ran
    through the balcony door into the kitchen, a bathroom's into the hall.
    Each colour is flooded on its own, from its own labels; then the colour pixels each run took
    are the markers of one last watershed that shares out the rest (lines, text, white)."""
    H, W = cost.shape
    cols, seed_cls = [], {}
    for i, t in enumerate(rooms_txt, 1):
        c = seed_colour(R, t['px'], int(0.35 * R.ppm))
        if c is None:
            continue
        k = next((k for k, q in enumerate(cols) if max(abs(a - b) for a, b in zip(c, q)) <= 6), None)
        if k is None:
            k = len(cols)
            cols.append(c)
        seed_cls[i] = k
    best = np.full((H, W), 255, np.uint8)
    cls = np.full((H, W), -1, np.int16)
    for k, c in enumerate(cols):
        d = cv2.absdiff(R.img, np.full_like(R.img, c)).max(axis=2)
        upd = d < best
        best[upd] = d[upd]
        cls[upd] = k
    cls[best > tol] = -1
    # (a fill is an area: the thin runs of a colour, the edges of text and lines, are not)
    k_fill = disk(max(2, int(0.05 * R.ppm)))
    for k in range(len(cols)):
        m = cls == k
        cls[m & ~cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, k_fill).astype(bool)] = -1
    # (the colour runs at a third of the resolution - 2.5 cm a pixel - for speed: they only place
    # the markers; the walls are kept whole by taking a block as free only when all of it is)
    f = 3
    Hs, Ws = H // f, W // f
    cls_s = cls[1:Hs * f:f, 1:Ws * f:f]
    free_s = cv2.erode(free.astype(np.uint8), np.ones((f, f), np.uint8))[1:Hs * f:f, 1:Ws * f:f].astype(bool)
    cost_s = cost[1:Hs * f:f, 1:Ws * f:f]
    mk_s = cv2.dilate(markers.astype(np.float32), np.ones((f, f), np.uint8))[1:Hs * f:f, 1:Ws * f:f].astype(np.int32)
    mk_s[~free_s] = 0
    M_s = np.zeros((Hs, Ws), np.int32)
    pad = int(1.0 * R.ppm / f)
    for k in range(len(cols)):
        ids = [i for i, kk in seed_cls.items() if kk == k]
        mine = cls_s == k
        ys, xs = np.nonzero(mine)
        if not ids or not len(xs):
            continue
        y0, y1 = max(0, ys.min() - pad), min(Hs, ys.max() + pad + 1)
        x0, x1 = max(0, xs.min() - pad), min(Ws, xs.max() + pad + 1)
        mk = mk_s[y0:y1, x0:x1]
        mk = np.where(np.isin(mk, ids), mk, 0)
        allowed = free_s[y0:y1, x0:x1] & (mine[y0:y1, x0:x1] | (cls_s[y0:y1, x0:x1] == -1))
        wk = watershed(cost_s[y0:y1, x0:x1], mk, mask=allowed)
        take = mine[y0:y1, x0:x1] & (wk > 0)
        M_s[y0:y1, x0:x1][take] = wk[take]
    # back to full size: a label's marker only on the pixels of its own colour
    M = np.zeros((H, W), np.int32)
    M[:Hs * f, :Ws * f] = np.kron(M_s, np.ones((f, f), np.int32))
    lut = np.full(int(markers.max()) + 1, -2, np.int16)
    for i, k in seed_cls.items():
        lut[i] = k
    M[(M > 0) & (cls != lut[M])] = 0
    M[~free] = 0
    # every label keeps its own seed (a white room's too)
    M[markers > 0] = markers[markers > 0]
    return watershed(cost, M, mask=free)


def fill_colour(R, m):
    """the flat colour of a room: the most common pastel colour in it"""
    px = R.img[m]
    if len(px) > 4000:
        px = px[:: len(px) // 4000]
    q = (px // 6).astype(np.int32)
    keyv = q[:, 0] * 10000 + q[:, 1] * 100 + q[:, 2]
    sat_ok = (px.max(axis=1).astype(int) > 150)
    if sat_ok.any():
        keyv = keyv[sat_ok]
    vals, cnt = np.unique(keyv, return_counts=True)
    v = vals[np.argmax(cnt)]
    return [int(v // 10000) * 6 + 3, int(v // 100 % 100) * 6 + 3, int(v % 100) * 6 + 3]


def box_colour(R, f):
    b = f['bbox']
    pix = R.pg.get_pixmap(dpi=300, clip=SH.pymupdf.Rect(b[0] - 1, b[1] - 0.6, b[2] + 1, b[3] + 0.6), alpha=False)
    sub = np.frombuffer(pix.samples, np.uint8).reshape(-1, 3)
    sub = sub[(sub.min(axis=1) > 120) & (sub.astype(int).max(axis=1) - sub.astype(int).min(axis=1) > 6) | (sub.min(axis=1) > 245)]
    if not len(sub):
        return None
    q = (sub // 6).astype(np.int32)
    keyv = q[:, 0] * 10000 + q[:, 1] * 100 + q[:, 2]
    vals, cnt = np.unique(keyv, return_counts=True)
    v = vals[np.argmax(cnt)]
    return [int(v // 10000) * 6 + 3, int(v // 100 % 100) * 6 + 3, int(v % 100) * 6 + 3]


def polys_of(mask, R, eps):
    out = []
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    for c in cs:
        if cv2.contourArea(c) < 0.0025 * R.ppm ** 2:
            continue
        a = cv2.approxPolyDP(c, max(1.0, eps * R.ppm), True)[:, 0, :].astype(float)
        if len(a) < 3:
            continue
        p = Polygon([R.plan(x, y) for x, y in square(a)]).buffer(0)
        for g in getattr(p, 'geoms', [p]):
            if g.geom_type != 'Polygon' or g.area < 0.003:
                continue
            for q in no_holes(g):
                ring = list(q.exterior.coords)[:-1]
                if not Polygon(ring).exterior.is_ccw:
                    ring = ring[::-1]
                out.append([[round(x, 3), round(y, 3)] for x, y in ring])
    return out


def no_holes(p, depth=0):
    from shapely.ops import split
    if p.geom_type != 'Polygon' or not p.interiors or depth > 30:
        return [p]
    c = Polygon(p.interiors[0]).representative_point()
    x0, y0, x1, y1 = p.bounds
    pieces = list(split(p, LineString([(c.x, y0 - 1), (c.x, y1 + 1)])).geoms)
    if len(pieces) < 2:
        pieces = list(split(p, LineString([(x0 - 1, c.y), (x1 + 1, c.y)])).geoms)
    out = []
    for q in pieces:
        out += no_holes(q, depth + 1)
    return out


def windows(R, glass, wall, taken):
    """each run of window glass -> a quad across the whole wall (plan), and its pixel mask"""
    out, mask = [], np.zeros(glass.shape, bool)
    cs, lab = comps(glass, int(0.02 * R.ppm ** 2))
    solid = wall | glass
    for i, st, cen in cs:
        x, y, w, h = st[0], st[1], st[2], st[3]
        horiz = w >= h
        L = (w if horiz else h) / R.ppm
        if L < 0.35:
            continue
        # the wall band across the glass at its middle: walk out both ways over solid pixels
        cx, cy = int(cen[0]), int(cen[1])
        def run(dx, dy):
            n = 0
            px, py = cx, cy
            while 0 <= px < R.W and 0 <= py < R.H and solid[py, px] and n < 0.9 * R.ppm:
                px += dx; py += dy; n += 1
            return n
        if horiz:
            a0, a1 = cy - run(0, -1) + 1, cy + run(0, 1) - 1
            r = (x, a0, x + w - 1, a1)
        else:
            a0, a1 = cx - run(-1, 0) + 1, cx + run(1, 0) - 1
            r = (a0, y, a1, y + h - 1)
        mask[r[1]:r[3] + 1, r[0]:r[2] + 1] = True
        q = [R.plan(r[0], r[1]), R.plan(r[2] + 1, r[1]), R.plan(r[2] + 1, r[3] + 1), R.plan(r[0], r[3] + 1)]
        q = [[round(a, 3), round(b, 3)] for a, b in q]
        if not Polygon(q).exterior.is_ccw:
            q = q[::-1]
        out.append(q)
    return out, mask & ~taken


def vector_leaves(pg, fr, rect):
    """the door leaves as the sheet draws them: dark red strokes (two long sides and the caps),
    joined where they touch; each leaf -> its two ends (plan). A dashed line or an axis drawn
    across a leaf cut its pixels in two - the strokes do not care."""
    segs = []
    for d in pg.get_drawings():
        if not d.get('color') or not rect.intersects(d['rect']):
            continue
        c = d['color']
        if not (0.62 <= c[0] <= 0.82 and c[1] < 0.08 and c[2] < 0.08) or d.get('fill'):
            continue
        for it in d['items']:
            if it[0] == 'l':
                a, b = fr.to_plan(it[1].x, it[1].y), fr.to_plan(it[2].x, it[2].y)
                if math.dist(a, b) > 1e-3:
                    segs.append(LineString([a, b]))
    if not segs:
        return []
    blobs = unary_union([g.buffer(0.03) for g in segs])
    out = []
    for b in getattr(blobs, 'geoms', [blobs]):
        mine = [g for g in segs if b.contains(g.interpolate(0.5, normalized=True))]
        pts = np.array([p for g in mine for p in g.coords], float)
        if len(pts) < 2:
            continue
        m = pts.mean(0)
        u = np.linalg.svd(pts - m, full_matrices=False)[2][0]
        t = (pts - m) @ u
        e0, e1 = pts[np.argmin(t)], pts[np.argmax(t)]
        out.append((e0, e1))
    return out


def door_swings(R, leaf, barrier, taken, leaves=None):
    """[x, y (the doorway's middle), x, y (half a metre into the side the door opens to), x, y (the
    hinge)]; from the leaves' ends (vector_leaves) when given, else from the leaf pixels"""
    out = []
    ends = []
    if leaves:
        for a, b in leaves:
            ends.append((np.array(R.px(*a), float), np.array(R.px(*b), float)))
    else:
        cs, lab = comps(leaf, int(0.004 * R.ppm ** 2))
        for i, st, cen in cs:
            ys, xs = np.nonzero(lab == i)
            pts = np.stack([xs, ys], 1).astype(float)
            if len(pts) < 8:
                continue
            # the leaf's two ends: the farthest pair along its main direction
            m = pts.mean(0)
            u = np.linalg.svd(pts - m, full_matrices=False)[2][0]
            t = (pts - m) @ u
            ends.append((pts[np.argmin(t)], pts[np.argmax(t)]))
    for e0, e1 in ends:
        L = math.dist(e0, e1) / R.ppm
        if not (0.35 < L < 1.25):
            continue
        # the hinge: the end beside a wall
        def wallness(p):
            x0, y0 = int(p[0]), int(p[1])
            r = int(0.12 * R.ppm)
            sub = barrier[max(0, y0 - r):y0 + r + 1, max(0, x0 - r):x0 + r + 1]
            return sub.mean() if sub.size else 0
        hinge, tip = (e0, e1) if wallness(e0) >= wallness(e1) else (e1, e0)
        v = tip - hinge
        best = None
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            d = np.array(d, float)
            if v @ d < 0.15 * np.linalg.norm(v):
                continue
            # along the doorway from the hinge: free; behind the hinge: wall
            span = [hinge + d * (s * R.ppm) for s in np.linspace(0.12, max(0.3, L * 0.8), 8)]
            fr_ = np.mean([not barrier[int(p[1]), int(p[0])] if 0 <= int(p[0]) < R.W and 0 <= int(p[1]) < R.H else 0 for p in span])
            # (looked for a few centimetres either side: some partitions are drawn as two lines with
            # the room's colour between them, and the hinge stands between the lines)
            dn = np.array([-d[1], d[0]])
            wall_near = lambda c: any(barrier[int(p[1]), int(p[0])] for o in (-0.06, -0.03, 0.0, 0.03, 0.06)
                                      for p in [c + dn * (o * R.ppm)] if 0 <= int(p[0]) < R.W and 0 <= int(p[1]) < R.H)
            bk = wall_near(hinge - d * (0.08 * R.ppm))
            # ...and the other jamb a leaf's width on: the doorway runs between two wall ends (a
            # leaf drawn at 45 degrees left the doorway's way ambiguous)
            fj = any(wall_near(hinge + d * ((L + e) * R.ppm)) for e in np.linspace(-0.12, 0.18, 7))
            score = fr_ + 0.5 * bk + 0.3 * (v @ d) / np.linalg.norm(v) + 0.8 * fj
            if best is None or score > best[0]:
                best = (score, d)
        if best is None:
            continue
        d = best[1]
        n = np.array([-d[1], d[0]])
        if (v @ n) < 0:
            n = -n
        mid = hinge + d * (L * R.ppm / 2)
        a = R.plan(*mid)
        b = R.plan(*(mid + n * 0.5 * R.ppm))
        h = R.plan(*hinge)
        out.append([round(a[0], 3), round(a[1], 3), round(b[0], 3), round(b[1], 3), round(h[0], 3), round(h[1], 3)])
    return out


def mask_geom(mask, R, grow=0.0):
    """a pixel mask as plan polygons with their holes (and grown by `grow` metres)"""
    cs, hier = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    if hier is None:
        return Polygon()
    hier = hier[0]
    for i, c in enumerate(cs):
        if hier[i][3] != -1 or len(c) < 3:
            continue
        holes = []
        j = hier[i][2]
        while j != -1:
            if len(cs[j]) >= 3:
                holes.append([R.plan(float(x), float(y)) for x, y in cs[j][:, 0, :]])
            j = hier[j][0]
        g = Polygon([R.plan(float(x), float(y)) for x, y in c[:, 0, :]], holes).buffer(0)
        if not g.is_empty:
            out.append(g)
    g = unary_union(out)
    return g.buffer(grow, join_style=2) if grow else g


def vector_plan(pg, fr, R, rooms, struct, windows_, parapets, glazing, swings, outline, barrier, wallmask=None, structmask=None):
    """Rooms and walls as the sheet draws them, from its vector fills: every room is hatched in its
    flat's colour (the hatch cut into strips, joined in tools/rp/vfill.py) right up to its walls,
    so each room's outline is the piece of fill round its label - exact, square, no pixels. The
    walls are what lies between the fills inside the building, less the shafts and stairwells
    (wider than 0.7 m), the doorways (the drawn leaf's span, jamb to jamb, through the wall), the
    windows, the glazing and the parapets; concrete where the sheet draws concrete.
    Returns (walls, struct) as hole-free plan polygons, or None where the sheet has no fills."""
    import vfill
    F = vfill.fills(pg, fr, R.rect)
    comps_ = [(col, q) for col, g in F.items() for q in getattr(g, 'geoms', [g]) if q.geom_type == 'Polygon' and q.area > 0.25]
    if len(comps_) < 5:
        return None
    # the doors as lines across their doorways (hinge to the leaf's far end)
    door_lines = []
    for q in swings:
        if len(q) < 6:
            continue
        m, h = np.array(q[:2], float), np.array(q[4:6], float)
        half = float(np.linalg.norm(m - h))
        if half < 0.2:
            continue
        u = (m - h) / half
        door_lines.append(LineString([tuple(h - u * 0.05), tuple(h + u * (2 * half + 0.05))]))
    cutters = unary_union([ln.buffer(0.01) for ln in door_lines]) if door_lines else None
    owners = {}
    for r in rooms:
        pt = Point(*r['at'])
        hit = next((i for i, (c, q) in enumerate(comps_) if q.contains(pt)), None)
        if hit is None:
            near = min(range(len(comps_)), key=lambda i: comps_[i][1].distance(pt))
            if comps_[near][1].distance(pt) < 0.3:
                hit = near
        if hit is not None:
            owners.setdefault(hit, []).append(r)
    for i, rs in owners.items():
        col, q = comps_[i]
        pieces = [q]
        if len(rs) > 1 and cutters is not None:
            cut = q.difference(cutters)
            pieces = [g for g in getattr(cut, 'geoms', [cut]) if g.geom_type == 'Polygon' and g.area > 0.2] or [q]
        for r in rs:
            pt = Point(*r['at'])
            g = next((g for g in pieces if g.contains(pt)), None) or min(pieces, key=lambda g: g.distance(pt))
            ring = list(g.exterior.simplify(0.003).coords)[:-1]
            if not Polygon(ring).exterior.is_ccw:
                ring = ring[::-1]
            r['poly'] = [[round(x, 3), round(y, 3)] for x, y in ring]
            r['measured'] = round(g.area, 2)
            r['colour'] = list(col)
            r['vector'] = True
    # rooms the sheet leaves white (no hatch - the two lower flats of block Б's third floor): the
    # space the drawn walls and doors close round the label
    if wallmask is not None and any(not r.get('vector') for r in rooms):
        Bg = Polygon(outline).buffer(0)
        free_g = Bg.difference(mask_geom(wallmask, R))
        if cutters is not None:
            free_g = free_g.difference(cutters)
        faces = [g for g in getattr(free_g, 'geoms', [free_g]) if g.geom_type == 'Polygon' and g.area > 0.4]
        for r in rooms:
            if r.get('vector') or r.get('stair') or not r['area']:
                continue
            pt = Point(*r['at'])
            g = next((g for g in faces if g.contains(pt)), None)
            if g is None or g.area > 1.6 * r['area'] + 1:
                continue
            g = g.buffer(-0.01, join_style=2).buffer(0.01, join_style=2).simplify(0.01)
            g = max(getattr(g, 'geoms', [g]), key=lambda x: x.area)
            ring = list(g.exterior.coords)[:-1]
            if not Polygon(ring).exterior.is_ccw:
                ring = ring[::-1]
            r['poly'] = [[round(x, 3), round(y, 3)] for x, y in ring]
            r['measured'] = round(g.area, 2)
            r['vector'] = 'walls'
    # the walls: the building less its floors
    floor = unary_union([q for _, q in comps_])
    B = Polygon(outline).buffer(0)
    solid = B.difference(floor.buffer(0.004, join_style=2))
    voids = solid.buffer(-0.35, join_style=2).buffer(0.36, join_style=2)
    # (the walls the sheet draws are no void, even beside one: block В's walk-in wardrobe, left
    # white, took its partitions and the concrete pier at its door with it, the lift shafts their
    # concrete; by the rooms only, but for the concrete - a stairwell's steps are drawn in the walls'
    # colour)
    if wallmask is not None:
        near_rooms = unary_union([Polygon(r['poly']).buffer(0.45, join_style=2) for r in rooms
                                  if r.get('poly') and not r.get('stair') and not re.match(r'^зинапоя', (r['name'] or '').lower())])
        voids = voids.difference(mask_geom(wallmask, R).intersection(near_rooms))
    if structmask is not None:
        voids = voids.difference(mask_geom(structmask, R))
    solid = solid.difference(voids)
    # (only where the sheet draws wall: a wardrobe or shelves left out of a room's hatch are no
    # wall - in a hall they shut the rooms beyond off)
    if wallmask is not None:
        solid = solid.intersection(mask_geom(wallmask, R, 0.04))
    # the doorways through it: across from floor to floor, along from jamb to jamb
    doorways = []
    for q in swings:
        if len(q) < 6:
            continue
        m, h = np.array(q[:2], float), np.array(q[4:6], float)
        n = np.array(q[2:4], float) - m
        n /= np.linalg.norm(n)
        half = float(np.linalg.norm(m - h))
        if half < 0.2:
            continue
        u = (m - h) / half
        def reach(sg):
            for s_ in np.arange(0.0, 0.96, 0.01):
                if floor.contains(Point(*(m + n * sg * s_))):
                    return s_
            return None
        sp, sm = reach(1), reach(-1)
        # (an outer wall with its insulation, at a balcony door, is up to 0.7 m thick)
        if sp is None or sm is None or sp + sm > 0.95:
            continue
        mid = m + n * (sp - sm) / 2
        def jamb(sg):
            for e in np.arange(half - 0.08, half + 0.2, 0.005):
                x, y = R.px(*(mid + u * sg * e))
                if 0 <= int(x) < R.W and 0 <= int(y) < R.H and barrier[int(y), int(x)]:
                    return e
            return half
        ea, eb = jamb(-1), jamb(1)
        a0, a1 = m + n * (sp + 0.01), m - n * (sm + 0.01)
        cut = Polygon([tuple(m - u * ea + n * (sp + 0.04)), tuple(m + u * eb + n * (sp + 0.04)),
                       tuple(m + u * eb - n * (sm + 0.04)), tuple(m - u * ea - n * (sm + 0.04))])
        solid = solid.difference(cut)
        doorways.append(cut)
    # (a door in a glazed wall - block А's balcony doors - goes through the glass too)
    if doorways:
        through_glass(unary_union(doorways), windows_, glazing, parapets)
    others = unary_union([Polygon(p).buffer(0) for p in windows_ + parapets + glazing] or [Polygon()])
    solid = solid.difference(others)
    conc = unary_union([Polygon(p).buffer(0) for p in struct] or [Polygon()]).intersection(solid)
    rest = solid.difference(conc)

    def rings(g):
        out = []
        for part in getattr(g, 'geoms', [g]):
            if part.geom_type != 'Polygon' or part.area < 0.003:
                continue
            for qq in no_holes(part):
                qq = qq.simplify(0.002)
                if qq.is_empty or qq.geom_type != 'Polygon' or qq.area < 0.003:
                    continue
                # (a film along a floor's edge, under 2.5 cm thick, is no wall)
                if qq.buffer(-0.0125).is_empty:
                    continue
                ring = list(qq.exterior.coords)[:-1]
                if not Polygon(ring).exterior.is_ccw:
                    ring = ring[::-1]
                out.append([[round(x, 3), round(y, 3)] for x, y in ring])
        return out
    return rings(rest), rings(conc), [[[round(x, 3), round(y, 3)] for x, y in list(d.exterior.coords)[:-1]] for d in doorways]


def through_glass(D, *lists):
    """the windows, glazing and parapets (lists of plan polygons, changed in place) with the
    openings D cut out of them (a little wider: the glass is often a few cm thicker than the cut)"""
    D = D.buffer(0.06, join_style=2)
    for lst in lists:
        kept = []
        for p_ in lst:
            g = Polygon(p_).buffer(0)
            if not g.intersects(D):
                kept.append(p_)
                continue
            for q_ in getattr(g.difference(D), 'geoms', [g.difference(D)]):
                if q_.geom_type == 'Polygon' and q_.area > 0.004:
                    ring = list(q_.exterior.coords)[:-1]
                    kept.append([[round(x, 3), round(y, 3)] for x, y in ring])
        lst[:] = kept


def rings_of(g):
    """plan polygons, hole-free, of a geometry (walls)"""
    out = []
    for part in getattr(g, 'geoms', [g]):
        if part.geom_type != 'Polygon' or part.area < 0.003:
            continue
        for qq in no_holes(part):
            qq = qq.simplify(0.002)
            if qq.is_empty or qq.geom_type != 'Polygon' or qq.area < 0.003 or qq.buffer(-0.0125).is_empty:
                continue
            ring = list(qq.exterior.coords)[:-1]
            if not Polygon(ring).exterior.is_ccw:
                ring = ring[::-1]
            out.append([[round(x, 3), round(y, 3)] for x, y in ring])
    return out


def thin_bars(pg, fr):
    """the thin outlined stretches of partition: dark brown rectangles 6-16 cm by 0.6-2.6 m, as
    (plan polygon, sliding) - a little redder, a sliding door (block В's walk-in wardrobes)"""
    thin = []
    for d in pg.get_drawings():
        c = d.get('color')
        if not c or d.get('fill') or c[2] > 0.03:
            continue
        slide = abs(c[0] - 0.72) <= 0.03 and abs(c[1] - 0.18) <= 0.03
        if not slide and (abs(c[0] - 0.58) > 0.03 or abs(c[1] - 0.15) > 0.03):
            continue
        for sp in __import__('vfill').subpaths(d):
            if len(sp) < 4:
                continue
            g = Polygon([fr.to_plan(q.x, q.y) for q in sp]).buffer(0)
            if g.is_empty or g.geom_type != 'Polygon':
                continue
            r = g.minimum_rotated_rectangle
            xs = list(r.exterior.coords)
            a_, b_ = math.dist(xs[0], xs[1]), math.dist(xs[1], xs[2])
            w, l = min(a_, b_), max(a_, b_)
            if 0.06 <= w <= 0.16 and 0.6 <= l <= 2.6 and g.area > 0.8 * w * l:
                thin.append((g, slide))
    return thin


def open_closed_rooms(pg, fr, plan):
    """A room of a flat the sheet draws no door into (block В's kitchen-living rooms open to the
    hall through a stretch of partition drawn as a thin outline - a wide opening): opened there, so
    that every room can be walked into. Where the sheet shows no such stretch, a 0.9 m doorway in
    the middle of the wall between the room and the nearest room that can be reached."""
    thin = thin_bars(pg, fr)
    swings = plan['swings']
    cuts = []
    # (two rooms with nothing drawn between them, a beam over the gap - block В 25's entrance hall
    # and hall, 0.5 m apart: an open way through, at least 0.7 m wide)
    solid_g = unary_union([Polygon(p).buffer(0) for k in ('walls', 'struct', 'windows', 'glazing', 'parapets') for p in plan[k]] +
                          [g for g, _ in thin] + [LineString([s_[4:6], s_[:2]]).buffer(0.03) for s_ in plan['swings'] if len(s_) >= 6])
    inside_g = Polygon(plan['slab']).buffer(0)
    def passage(a, b):
        # (rooms closer than 0.3 m have a partition between them, drawn or not)
        if not 0.3 <= a.distance(b) <= 0.6:
            return None
        strip = a.buffer(0.6, join_style=2).intersection(b.buffer(0.6, join_style=2)).intersection(inside_g).difference(a).difference(b)
        free = strip.difference(solid_g.buffer(0.02, join_style=2))
        for part in getattr(free, 'geoms', [free]):
            if part.geom_type != 'Polygon' or part.distance(a) > 0.03 or part.distance(b) > 0.03:
                continue
            xs = list(part.minimum_rotated_rectangle.exterior.coords)
            if max(math.dist(xs[0], xs[1]), math.dist(xs[1], xs[2])) >= 0.7:
                return part
        return None
    for apt in plan['apartments']:
        rs = apt['rooms'] + apt['balconies']
        G = [Polygon(r['poly']).buffer(0) for r in rs]
        dws = [Polygon(d).buffer(0) for d in plan.get('doorways', [])]
        def linked(i, j):
            if G[i].distance(G[j]) < 0.04:
                return True
            if any(G[i].distance(d) < 0.06 and G[j].distance(d) < 0.06 for d in dws + cuts):
                return True
            way = passage(G[i], G[j])
            if way is not None:
                cuts.append(way.buffer(0.01, join_style=2))
                return True
            return False
        for _ in range(4):
            start = max(range(len(rs)), key=lambda i: (rs[i]['kind'] == 'hall', G[i].area))
            seen, todo = {start}, [start]
            while todo:
                i = todo.pop()
                for j in range(len(rs)):
                    if j not in seen and linked(i, j):
                        seen.add(j)
                        todo.append(j)
            lost = [i for i in range(len(rs)) if i not in seen and not (rs[i]['kind'] in ('loggia', 'terrace') and rs[i]['area'] <= 2.6)]
            if not lost:
                break
            made = False
            for i in sorted(lost, key=lambda i: -G[i].area):
                # (a sliding door may stand off the room's fill: block В 25 ends the wardrobe's fill
                # at the beam over its opening, 0.38 m short of the door)
                near = sorted((G[i].distance(G[j]), j) for j in seen if G[i].distance(G[j]) < 0.3 or
                              any(g.distance(G[i]) < 0.45 and g.distance(G[j]) < 0.06 for g, _ in thin))
                if not near:
                    continue
                j = near[0][1]
                t = [(g, sl) for g, sl in thin if g.distance(G[i]) < 0.45 and g.distance(G[j]) < 0.06]
                if t:
                    g, sl = max(t, key=lambda x: x[0].area)
                    cut = g.buffer(0.05, join_style=2)
                    gap = g.distance(G[i])
                    if gap > 0.01:
                        # the stretch between the door and the room, as wide as the door
                        xs = np.array(g.minimum_rotated_rectangle.exterior.coords[:4])
                        e = [xs[1] - xs[0], xs[2] - xs[1]]
                        u, n = (e[0], e[1]) if np.linalg.norm(e[0]) >= np.linalg.norm(e[1]) else (e[1], e[0])
                        u, n = u / np.linalg.norm(u), n / np.linalg.norm(n)
                        c = np.array(g.centroid.coords[0])
                        if np.dot(np.array(G[i].centroid.coords[0]) - c, n) < 0:
                            n = -n
                        L = float(max(abs(np.dot(xs - c, u))))
                        W = float(max(abs(np.dot(xs - c, n))))
                        cut = cut.union(Polygon([tuple(c - u * L), tuple(c + u * L), tuple(c + u * L + n * (W + gap + 0.04)),
                                                 tuple(c - u * L + n * (W + gap + 0.04))]))
                    if sl:
                        rs[i]['slide'] = True
                else:
                    strip = G[i].buffer(0.3, join_style=2).intersection(G[j].buffer(0.3, join_style=2)).difference(G[i]).difference(G[j])
                    if strip.is_empty:
                        continue
                    strip = max(getattr(strip, 'geoms', [strip]), key=lambda g: g.area)
                    c = strip.centroid
                    cut = strip.intersection(Point(c.x, c.y).buffer(0.45, cap_style=3)).buffer(0.03, join_style=2)
                cuts.append(cut)
                made = True
                break
            if not made:
                break
    if not cuts:
        return
    C = unary_union(cuts)
    plan['walls'] = rings_of(unary_union([Polygon(w).buffer(0) for w in plan['walls']]).difference(C))
    plan['struct'] = rings_of(unary_union([Polygon(w).buffer(0) for w in plan['struct']]).difference(C))
    # (block А's loggias: the sheet draws the bedroom's wall onto them all glass, with no door)
    through_glass(C, plan['windows'], plan['glazing'], plan['parapets'])
    for cut in cuts:
        g = cut.simplify(0.003)
        if g.geom_type == 'Polygon':
            plan.setdefault('doorways', []).append([[round(x, 3), round(y, 3)] for x, y in list(g.exterior.coords)[:-1]])
    # the flats' outlines again, through the new openings
    dws = [Polygon(d).buffer(0) for d in plan['doorways']]
    for apt in plan['apartments']:
        gp = [Polygon(r['poly']).buffer(0) for r in apt['rooms'] + apt['balconies']]
        mine = [d for d in dws if sum(1 for q in gp if q.distance(d) < 0.06) >= 2]
        o = unary_union([q.buffer(0.16, join_style=2) for q in gp] + [d.buffer(0.02, join_style=2) for d in mine]).buffer(-0.04, join_style=2)
        if o.geom_type != 'Polygon':
            o = max(o.geoms, key=lambda q: q.area)
        ring = list(o.simplify(0.02).exterior.coords)[:-1]
        if not Polygon(ring).exterior.is_ccw:
            ring = ring[::-1]
        apt['outline'] = [[round(x, 3), round(y, 3)] for x, y in ring]


def square_doorways(rooms, walls, struct, swings):
    """At every door the sheet draws, the two rooms meet on the wall's line, straight across the
    doorway: the watershed let the line between them run along the drawn leaf (half open into one
    room), and the viewer then walled the doorway up along that slant - the rooms behind it could
    not be walked into. The leaf is drawn from its hinge, on the face of the wall on the side it
    opens to: that face is the line; the wall's thickness (where the walls each side of the gap
    show it, else 12 cm) is the doorway's slab, left to neither room; in front of the doorway, as
    wide as the leaf and 0.9 m deep, the floor is the room's on that side (less any wall)."""
    Wg = unary_union([Polygon(p).buffer(0) for p in walls + struct])
    W = prep(Wg)
    polys = [Polygon(r['poly']).buffer(0) for r in rooms]
    done = 0
    for q in swings:
        if len(q) < 6:
            continue
        m = np.array(q[:2], float)
        n = np.array(q[2:4], float) - m
        n /= np.linalg.norm(n)
        d = np.array([-n[1], n[0]])
        h = np.array(q[4:6], float)
        half = float(np.linalg.norm(h - m))
        if not 0.25 <= half <= 0.65:
            continue
        sh = float((h - m) @ n)
        # the wall's thickness: offsets behind the face with wall just beyond the gap's ends
        wall_at = lambda s_: any(W.contains(Point(*(m + n * s_ + d * sg * (half + 0.06)))) for sg in (-1, 1))
        t = 0.0
        while t < 0.45 and wall_at(sh - t - 0.01):
            t += 0.02
        t = max(t, 0.12) if t < 0.06 else t
        # (the rooms each side: looked for a little way in - the drawn leaf may keep its room's
        # outline off the doorway)
        def side(sg, base):
            for depth in (0.25, 0.4, 0.6, 0.85):
                for off in (0.0, -half / 2, half / 2):
                    pt = Point(*(m + n * sg * (base + depth) + d * off))
                    i = next((i for i, g in enumerate(polys) if g.contains(pt)), None)
                    if i is not None:
                        return i
            return None
        ia, ib = side(1, sh), side(-1, t - sh)
        if ia is None or ib is None or ia == ib:
            continue
        # (the gap between the jambs, a little wider than the leaf: found in the middle of the wall)
        def jamb(sg):
            for e in np.arange(half - 0.1, half + 0.25, 0.01):
                if W.contains(Point(*(m + n * (sh - t / 2) + d * sg * e))):
                    return e
            return half + 0.03
        e0, e1 = -jamb(-1), jamb(1)
        box_ = lambda a, b: Polygon([m + d * e0 + n * a, m + d * e1 + n * a, m + d * e1 + n * b, m + d * e0 + n * b])
        zp, zm, slab = box_(sh, sh + 0.9), box_(sh - t - 0.9, sh - t), box_(sh - t, sh)
        others = unary_union([g for i, g in enumerate(polys) if i not in (ia, ib)] or [Polygon()])
        # (only where the two rooms are, give or take the sliver along the drawn leaf: the zone
        # in front of a doorway may reach through a thin partition into the next flat)
        U = polys[ia].union(polys[ib]).buffer(0.12)
        fa = zp.intersection(U).difference(Wg).difference(others)
        fb = zm.intersection(U).difference(Wg).difference(others)
        new = {ia: polys[ia].union(fa).difference(zm).difference(slab), ib: polys[ib].union(fb).difference(zp).difference(slab)}
        ok = True
        for i, g in new.items():
            g = g.buffer(0.004, join_style=2).buffer(-0.004, join_style=2)
            g = max(getattr(g, 'geoms', [g]), key=lambda x: x.area) if not g.is_empty else g
            if g.is_empty or g.area < 0.6 * polys[i].area:
                ok = False
                break
            new[i] = g
        if not ok:
            continue
        for i, g in new.items():
            polys[i] = g
            ring = list(g.simplify(0.003).exterior.coords)[:-1]
            if not Polygon(ring).exterior.is_ccw:
                ring = ring[::-1]
            rooms[i]['poly'] = [[round(x, 3), round(y, 3)] for x, y in ring]
        done += 1
    return done


def facade_pilasters(R, building):
    """the white pilasters on the facades: grey U-shaped outlines standing on the outside of the
    outer walls, closed against the wall and filled"""
    grey = R.cls('grey', 26) & ~building
    edge = cv2.dilate(building.astype(np.uint8), sq(5)).astype(bool) & ~building
    m = cv2.morphologyEx((grey | edge).astype(np.uint8), cv2.MORPH_CLOSE, sq(5))
    m = ndi.binary_fill_holes(m) & ~building
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, sq(int(0.12 * R.ppm))).astype(bool)
    out = []
    for q in polys_of(m, R, 0.02):
        P_ = Polygon(q)
        x0, y0, x1, y1 = P_.bounds
        if 0.15 < min(x1 - x0, y1 - y0) < 1.2 and max(x1 - x0, y1 - y0) < 2.5:
            out.append([[round(x0, 3), round(y0, 3)], [round(x1, 3), round(y0, 3)], [round(x1, 3), round(y1, 3)], [round(x0, 3), round(y1, 3)]])
    return out


def lift_crosses(pg, R, rooms):
    """the lift cars: the black X drawn in each shaft (two diagonals crossing at their middles).
    c, w (along the door wall), d, f (out of the doors, towards the lift hall), q (kg)"""
    segs = []
    for dr in pg.get_drawings():
        if not R.rect.contains(dr['rect']) or not dr.get('color') or max(dr['color']) > 0.05:
            continue
        for it in dr['items']:
            if it[0] != 'l':
                continue
            a, b = R.fr.to_plan(it[1].x, it[1].y), R.fr.to_plan(it[2].x, it[2].y)
            L = math.dist(a, b)
            ang = abs(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))) % 90
            if 1.4 < L < 4.0 and 20 < ang < 70:
                segs.append((a, b))
    halls = [Polygon(r['poly']).buffer(0) for r in rooms if r['common'] and not r.get('stair')]
    out, used = [], set()
    for i, (a, b) in enumerate(segs):
        for j, (c, d) in enumerate(segs):
            if j <= i or i in used or j in used:
                continue
            m1 = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            m2 = ((c[0] + d[0]) / 2, (c[1] + d[1]) / 2)
            if math.dist(m1, m2) > 0.12 or not LineString([a, b]).crosses(LineString([c, d])):
                continue
            xs = [a[0], b[0], c[0], d[0]]
            ys = [a[1], b[1], c[1], d[1]]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            if not (1.0 < w < 3.2 and 1.0 < h < 3.2):
                continue
            used |= {i, j}
            cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
            best = None
            for f, (dx, dy) in ((0.0, (1, 0)), (math.pi, (-1, 0)), (math.pi / 2, (0, 1)), (-math.pi / 2, (0, -1))):
                half = (w if dx else h) / 2
                p = Point(cx + dx * (half + 0.6), cy + dy * (half + 0.6))
                dmin = min((hp.distance(p) for hp in halls), default=9)
                if best is None or dmin < best[0]:
                    best = (dmin, f, (h if dx else w), (w if dx else h))
            _, f, along, across = best
            q = 1000 if along * across > 3.6 else 630
            out.append(dict(c=[round(cx, 3), round(cy, 3)], w=round(along, 3), d=round(across, 3), f=round(f, 4), q=q,
                            shaft=[[round(min(xs), 3), round(min(ys), 3)], [round(max(xs), 3), round(min(ys), 3)],
                                   [round(max(xs), 3), round(max(ys), 3)], [round(min(xs), 3), round(max(ys), 3)]]))
    return out


def lift_cars(R, shafts, rooms):
    """the lift shafts (the grey cross drawn in them): c, w along the door wall, d, f out of the
    doors (towards the lift hall), q (kg) by the size of the car"""
    grey = R.cls('black', 60) | R.cls('grey', 30)
    halls = [Polygon(r['poly']) for r in rooms if r['common']]
    out = []
    for part in shafts:
        ys, xs = np.nonzero(part)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        w, h = (x1 - x0 + 1) / R.ppm, (y1 - y0 + 1) / R.ppm
        if not (1.2 < w < 3.4 and 1.2 < h < 3.4):
            continue
        sub = grey[y0:y1 + 1, x0:x1 + 1]
        # the cross: grey on both diagonals
        n = 40
        thick = cv2.dilate(sub.astype(np.uint8), sq(7)).astype(bool)
        hy, hx = sub.shape[0] - 1, sub.shape[1] - 1
        d1 = np.mean([thick[int(i * hy / n), int(i * hx / n)] for i in range(4, n - 3)])
        d2 = np.mean([thick[int(i * hy / n), hx - int(i * hx / n)] for i in range(4, n - 3)])
        if min(d1, d2) < 0.6:
            continue
        cx, cy = R.plan((x0 + x1) / 2, (y0 + y1) / 2)
        # which side faces a hall
        best = None
        for f, (dx, dy) in ((0.0, (1, 0)), (math.pi, (-1, 0)), (math.pi / 2, (0, 1)), (-math.pi / 2, (0, -1))):
            half = (w if dx else h) / 2
            p = Point(cx + dx * (half + 0.5), cy + dy * (half + 0.5))
            dmin = min((hp.distance(p) for hp in halls), default=9)
            if best is None or dmin < best[0]:
                best = (dmin, f, (h if dx else w), (w if dx else h))
        _, f, along, across = best
        q = 1000 if along >= 2.0 and across >= 1.9 else 630
        out.append(dict(c=[round(cx, 3), round(cy, 3)], w=round(along, 3), d=round(across, 3), f=round(f, 4), q=q))
    return out


# --------------------------------------------------------------------------- flats

def group_flats(plan, R):
    rooms = [r for r in plan['rooms_raw'] if not r['common']]
    common = [r for r in plan['rooms_raw'] if r['common']]
    P = {r['i']: Polygon(r['poly']).buffer(0) for r in rooms}
    dist = lambda a, b: P[a['i']].distance(P[b['i']])
    lav = lambda r: r['kind'] in ('loggia', 'terrace') or max(abs(a - b) for a, b in zip(r['colour'], BALCONY)) <= 10
    greyish = lambda r: max(r['colour']) - min(r['colour']) < 8 and r['colour'][0] < 236
    loose_ = lambda r: lav(r) or greyish(r)
    same = lambda a, b: max(abs(x - y) for x, y in zip(a['colour'], b['colour'])) <= 14
    doors = []
    for s_ in plan['swings']:
        m, n = np.array(s_[:2]), np.array(s_[2:4]) - np.array(s_[:2])
        n = n / (np.linalg.norm(n) or 1)
        doors.append((Point(*m), Point(*(m + n * 0.35)), Point(*(m - n * 0.35))))

    def linked(a, b):
        d = dist(a, b)
        if d < 0.04:
            return True     # open to each other
        if d > 0.5:
            return False
        pa, pb = P[a['i']], P[b['i']]
        return any(pa.distance(m) < 0.4 and pb.distance(m) < 0.4 and
                   ((pa.distance(p1) < 0.12 and pb.distance(p2) < 0.12) or (pb.distance(p1) < 0.12 and pa.distance(p2) < 0.12))
                   for m, p1, p2 in doors)
    parent = {r['i']: r['i'] for r in rooms}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    core = [r for r in rooms if not loose_(r)]
    ban = {frozenset(x) for x in NO_LINK.get(plan['key'], [])}
    for a in core:
        for b in core:
            if a['i'] < b['i'] and same(a, b) and linked(a, b) and frozenset((a['area'], b['area'])) not in ban:
                if os.environ.get('LINKS'):
                    print('   link', a['name'] or '?', a['area'], '-', b['name'] or '?', b['area'], round(dist(a, b), 2))
                parent[find(a['i'])] = find(b['i'])
    groups = {}
    for r in core:
        groups.setdefault(find(r['i']), []).append(r)
    groups = list(groups.values())
    loose = [r for r in rooms if loose_(r)]
    # match the flat boxes to groups by colour, then by distance; a flat cut in two (a door the
    # drawing gives no leaf) is the box's group plus the rest of its colour next to it
    boxes = [f for f in plan['flats_raw'] if f.get('area')]
    gcol = lambda g: max(g, key=lambda r: r['area'])['colour']
    gcen = lambda g: unary_union([P[r['i']] for r in g]).centroid
    # one box per group, all at once (least total cost): colour, distance, and the area the box says
    from scipy.optimize import linear_sum_assignment
    C = np.full((len(groups), len(boxes)), 1e6)
    for gi, g in enumerate(groups):
        c, ga = gcen(g), sum(r['area'] for r in g)
        for j, f in enumerate(boxes):
            if not f['colour']:
                continue
            dc = max(abs(x - y) for x, y in zip(gcol(g), f['colour']))
            C[gi, j] = 30 * (dc > 24) + 0.3 * dc + 0.6 * math.dist((c.x, c.y), f['at']) + 0.15 * abs(f['area'] * 0.9 - ga)
    gbox = {}
    if len(groups) and len(boxes):
        for gi, j in zip(*linear_sum_assignment(C)):
            if C[gi, j] < 1e5:
                gbox[gi] = j
    flats = {j: list(groups[gi]) for gi, j in gbox.items()}
    rest = [groups[gi] for gi in range(len(groups)) if gi not in gbox]
    deficit = lambda j: boxes[j]['area'] - sum(r['area'] for r in flats[j])
    for g in sorted(rest, key=lambda g: -sum(r['area'] for r in g)):
        area = sum(r['area'] for r in g)
        cands = [(abs(deficit(j) - area), j) for j in flats
                 if same(g[0], flats[j][0]) and min(dist(a, b) for a in g for b in flats[j]) < 0.5]
        cands = cands or [(abs(deficit(j) - area) + 5 * min(dist(a, b) for a in g for b in flats[j]), j) for j in flats
                          if min(dist(a, b) for a in g for b in flats[j]) < 0.5]
        if cands:
            flats[min(cands)[1]] += g
        else:
            loose += g
    # a flat with more rooms than its area: the unnamed space that is no part of it (a vestibule)
    for j in flats:
        if deficit(j) > -0.3:
            continue
        near_loose = [r for r in loose if min(dist(r, x) for x in flats[j]) < 0.6]
        fills = [0.0] + [r['area'] for r in near_loose] + [a['area'] + b['area'] for a in near_loose for b in near_loose if a is not b]
        for r in sorted([r for r in flats[j] if not r['name']], key=lambda r: -r['area']):
            d = deficit(j) + r['area']
            if d > -0.3 and any(abs(d - f) < 0.3 for f in fills):
                flats[j].remove(r)
                r['common'] = True
                common.append(r)
                break
    # (which rooms each drawn door joins: the rooms a little way in on either side of it)
    door_pairs = set()
    for s_ in plan['swings']:
        m_, n_ = np.array(s_[:2], float), np.array(s_[2:4], float) - np.array(s_[:2], float)
        n_ /= (np.linalg.norm(n_) or 1)
        sides = []
        for sg in (1, -1):
            hit = None
            for depth in (0.2, 0.35, 0.5, 0.7, 0.9):
                pt = Point(*(m_ + n_ * sg * depth))
                hit = next((rr['i'] for rr in rooms if P[rr['i']].contains(pt)), None)
                if hit is not None:
                    break
            sides.append(hit)
        if None not in sides and sides[0] != sides[1]:
            door_pairs.add(frozenset(sides))
    # balconies and rooms of no flat colour: to the flat whose room has the door drawn into them;
    # else to the flat next to them that misses that much area
    for r in sorted(loose, key=lambda r: -r['area']):
        by_door = [j for j in flats if any(frozenset((r['i'], x['i'])) in door_pairs for x in flats[j])]
        if len(by_door) == 1 and deficit(by_door[0]) > r['area'] - 0.25:
            flats[by_door[0]].append(r)
            continue
        near = [(min(dist(r, x) for x in flats[j]), j) for j in flats]
        near = [(d, j) for d, j in near if d < 0.6]
        if not near:
            continue
        fit = [(abs(deficit(j) - r['area']), d, j) for d, j in near if deficit(j) > r['area'] - 0.25]
        j = min(fit)[2] if fit else min(near)[1]
        flats[j].append(r)
    # repair: a room in a flat with too much area that another flat beside it misses exactly
    for _ in range(3):
        moved = False
        for j in flats:
            if deficit(j) > -0.3:
                continue
            for r in sorted(flats[j], key=lambda r: r['area']):
                for k in flats:
                    if k == j or abs(deficit(k) - r['area']) > 0.25 or min(dist(r, x) for x in flats[k]) > 0.5:
                        continue
                    flats[j].remove(r)
                    flats[k].append(r)
                    moved = True
                    break
                if moved:
                    break
        if not moved:
            break
    # a small unnamed space the flat has too much of: a vestibule or service room of the floor
    for j in flats:
        sur = -deficit(j) - (boxes[j].get('terrace') or 0)
        if sur < 0.3:
            continue
        cand = [r for r in flats[j] if not r['name'] and abs(r['area'] - sur) < 0.3]
        if cand:
            r = cand[0]
            flats[j].remove(r)
            r['common'] = True
            common.append(r)
    # an unnamed room (a bathroom) left to the floor whose door the sheet draws from one flat's
    # room, that flat missing just its area: that flat's
    for r in list(common):
        if r['name'] or r.get('stair'):
            continue
        by_door = [j for j in flats if any(frozenset((r['i'], x['i'])) in door_pairs for x in flats[j])]
        if len(by_door) == 1 and abs(deficit(by_door[0]) - r['area']) < 0.3:
            common.remove(r)
            r['common'] = False
            flats[by_door[0]].append(r)
    for area, want in FORCE.get(plan['key'], {}).items():
        j = next((j for j in flats if abs(boxes[j]['area'] - area) < 0.01), None)
        if j is None:
            continue
        pool = [(r, k) for k in flats for r in flats[k]] + [(r, None) for r in loose] + \
            [(r, None) for r in common if not r['name'] and not r.get('stair')]
        got = []
        for a_ in want:
            c = [(r, k) for r, k in pool if abs(r['area'] - a_) < 0.01 and r not in got]
            if not c:
                continue
            r, k = min(c, key=lambda rk: Point(boxes[j]['at']).distance(P[rk[0]['i']]))
            got.append(r)
            if k is not None:
                flats[k].remove(r)
            elif r in loose:
                loose.remove(r)
            if r in common:
                common.remove(r)
                r['common'] = False
        dropped = [r for r in flats[j] if r not in got]
        flats[j] = got
        # (what the list leaves out goes to the flat beside it that misses that much)
        for r in dropped:
            fit = [(abs(deficit(k) - r['area']), k) for k in flats if k != j and min(dist(r, x) for x in flats[k]) < 0.6 and deficit(k) > r['area'] - 0.3]
            if fit:
                flats[min(fit)[1]].append(r)
    for g in flats.values():
        split_open([r for r in g if not loose_(r)])
    out = [(flats[j], boxes[j], max(abs(x - y) for x, y in zip(gcol([r for r in flats[j] if not loose_(r)] or flats[j]), boxes[j]['colour'])) > 16)
           for j in sorted(flats)]
    plan['flat_match'] = [dict(rooms=[r['name'] for r in g], box=f, colour_mismatch=bad) for g, f, bad in out]
    apartments = []
    for g, f, bad in out:
        rooms_out, balconies = [], []
        for r in sorted(g, key=lambda r: -r['area']):
            kind = r['kind']
            if kind is None:
                kind = 'loggia' if lav(r) and r['area'] < 12 else 'bath' if r['area'] < 9 else 'storage'
            if kind == 'loggia' and r['area'] >= 12:
                kind = 'terrace'
            en, ru, tjn = NAMES[kind]
            item = dict(name=en, ru=ru, tj=tjn, kind=kind, area=r['area'], poly=r['poly'], label=r['name'])
            (balconies if kind == 'terrace' else rooms_out).append(item)
        # (the rooms and the doorways between them: the outline of a flat whose rooms the sheet's
        # fills give exactly, a thick wall apart, stays one piece through its doors)
        gp = [Polygon(r['poly']).buffer(0) for r in g]
        dws = [Polygon(dw).buffer(0) for dw in plan.get('doorways', []) if sum(1 for q in gp if q.distance(Polygon(dw)) < 0.05) >= 2]
        outline = unary_union([q.buffer(0.16, join_style=2) for q in gp] + [d.buffer(0.02, join_style=2) for d in dws]).buffer(-0.04, join_style=2)
        if outline.geom_type != 'Polygon':
            outline = max(outline.geoms, key=lambda q: q.area)
        ring = list(outline.simplify(0.02).exterior.coords)[:-1]
        if not Polygon(ring).exterior.is_ccw:
            ring = ring[::-1]
        apartments.append(dict(colour='#%02x%02x%02x' % tuple(g[0]['colour']), rooms_count=f['rooms'], label_rooms=f['rooms'],
                               area=f['area'], terrace_area=f.get('terrace'), outline=[[round(x, 3), round(y, 3)] for x, y in ring],
                               rooms=rooms_out, balconies=balconies, furniture=[], box=f['at']))
    plan['apartments'] = apartments
    shafts = unary_union([Polygon(lf['shaft']).buffer(0.08, join_style=2) for lf in plan['lifts']]) if plan['lifts'] else None
    for c in common:
        if shafts is not None:
            q = Polygon(c['poly']).buffer(0).difference(shafts)
            if not q.is_empty:
                q = max(getattr(q, 'geoms', [q]), key=lambda g: g.area)
                ring = list(q.simplify(0.01).exterior.coords)[:-1]
                if not Polygon(ring).exterior.is_ccw:
                    ring = ring[::-1]
                c['poly'] = [[round(x, 3), round(y, 3)] for x, y in ring]
    plan['common'] = [c['poly'] for c in common]
    plan['common_rooms'] = [dict(name=c['name'], area=c['area'], poly=c['poly']) for c in common]


def split_open(rooms):
    """Rooms of a flat open to each other with no wall (kitchen and living room): the watershed's
    boundary between them wanders; cut their union straight, across the line between the two labels
    (along the nearer plan axis), where the areas come out in the ratio of the labelled areas."""
    for _ in range(2):
        for a in rooms:
            for b in rooms:
                if a is b or id(a) > id(b):
                    continue
                pa, pb = Polygon(a['poly']).buffer(0), Polygon(b['poly']).buffer(0)
                shared = pa.buffer(0.03).intersection(pb.buffer(0.03)).area / 0.06
                if shared < 1.3:
                    continue
                u = pa.union(pb).buffer(0.05, join_style=2).buffer(-0.05, join_style=2)
                if u.geom_type != 'Polygon':
                    continue
                (ax_, ay_), (bx_, by_) = a['at'], b['at']
                vert = abs(bx_ - ax_) >= abs(by_ - ay_)
                want = a['area'] / (a['area'] + b['area'])
                x0, y0, x1, y1 = u.bounds
                lo, hi = (min(ax_, bx_), max(ax_, bx_)) if vert else (min(ay_, by_), max(ay_, by_))
                a_low = (ax_ < bx_) if vert else (ay_ < by_)
                def part(c):
                    half = box(x0 - 1, y0 - 1, c, y1 + 1) if vert else box(x0 - 1, y0 - 1, x1 + 1, c)
                    low = u.intersection(half)
                    return low if a_low else u.difference(half)
                for _ in range(40):
                    c = (lo + hi) / 2
                    fa = part(c).area / u.area
                    if (fa < want) == a_low:
                        lo = c
                    else:
                        hi = c
                qa, qb = part(c), u.difference(part(c))
                if qa.is_empty or qb.is_empty:
                    continue
                qa = max(getattr(qa, 'geoms', [qa]), key=lambda g: g.area)
                qb = max(getattr(qb, 'geoms', [qb]), key=lambda g: g.area)
                for r, q in ((a, qa), (b, qb)):
                    ring = list(q.simplify(0.004).exterior.coords)[:-1]
                    if not Polygon(ring).exterior.is_ccw:
                        ring = ring[::-1]
                    r['poly'] = [[round(x, 3), round(y, 3)] for x, y in ring]
                    r['measured'] = round(q.area, 2)
                    r['open_to'] = (b if r is a else a)['name']


# --------------------------------------------------------------------------- check picture

def draw_debug(key, plan, R, ws):
    os.makedirs(DBG, exist_ok=True)
    img = (255 - (255 - R.img.astype(np.float32)) * 0.35).astype(np.uint8).copy()
    rng = np.random.default_rng(3)

    def P(pts):
        return np.array([R.px(x, y) for x, y in pts], np.int32)
    for a in plan['apartments']:
        c = tuple(int(v) for v in rng.integers(40, 220, 3))
        for r in a['rooms'] + a['balconies']:
            cv2.fillPoly(img, [P(r['poly'])], c)
            cv2.polylines(img, [P(r['poly'])], True, (0, 0, 0), 2)
        cv2.polylines(img, [P(a['outline'])], True, (255, 0, 0), 4)
    for c in plan['common']:
        cv2.fillPoly(img, [P(c)], (200, 200, 200))
    for w in plan['walls']:
        cv2.fillPoly(img, [P(w)], (90, 60, 40))
    for w in plan['struct']:
        cv2.fillPoly(img, [P(w)], (180, 0, 180))
    for w in plan['windows']:
        cv2.fillPoly(img, [P(w)], (0, 160, 255))
    for w in plan['glazing']:
        cv2.fillPoly(img, [P(w)], (0, 230, 230))
    for s in plan['swings']:
        a, b = R.px(s[0], s[1]), R.px(s[2], s[3])
        cv2.arrowedLine(img, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (255, 0, 0), 4, tipLength=0.3)
    import math as _m
    for a in plan['apartments']:
        for it in a['furniture']:
            if it['type'] in ('rug',):
                continue
            if it['type'] == 'sofa':
                q = [b[:4] + [b[6]] for b in it['boxes']]
            elif it['type'] == 'bed':
                q = [it['c'] + [it['l'], it['w'], it['f']]]
            elif it['type'] in ('dining', 'ctable'):
                q = [it['c'] + [it['w'], it['d'], it['a']]] + [[x, y, 0.42, 0.42, 0] for x, y, _ in it.get('chairs', [])]
            else:
                q = [it['c'] + [it['w'], it['d'], it['f'] + _m.pi / 2]]
            for cx, cy, w, d, ang in q:
                u, v = (_m.cos(ang), _m.sin(ang)), (-_m.sin(ang), _m.cos(ang))
                pts = [(cx + u[0] * sw * w / 2 + v[0] * sd * d / 2, cy + u[1] * sw * w / 2 + v[1] * sd * d / 2) for sw, sd in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                cv2.polylines(img, [P(pts)], True, (230, 0, 0), 3)
            if 'f' in it and it['type'] != 'sofa':
                a0 = R.px(*it['c'])
                a1 = R.px(it['c'][0] + _m.cos(it['f']) * 0.5, it['c'][1] + _m.sin(it['f']) * 0.5)
                cv2.arrowedLine(img, (int(a0[0]), int(a0[1])), (int(a1[0]), int(a1[1])), (0, 150, 0), 3, tipLength=0.4)
            if 'c' in it:
                cv2.putText(img, it['type'][:4], (int(R.px(*it['c'])[0]) - 20, int(R.px(*it['c'])[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 0, 0), 2)
    for lf in plan['lifts']:
        c = R.px(*lf['c'])
        cv2.putText(img, f"{lf['q']}", (int(c[0]) - 40, int(c[1])), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 0), 3)
    for r in plan['rooms_raw']:
        c = R.px(*r['at'])
        ok = abs(r['measured'] - r['area']) / max(r['area'], 1) < 0.08
        cv2.putText(img, f"{r['measured']:.1f}/{r['area']:.1f}", (int(c[0]) - 60, int(c[1]) + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                    (0, 120, 0) if ok else (255, 0, 0), 3)
    cv2.imwrite(os.path.join(DBG, f'{key}.png'), cv2.cvtColor(cv2.resize(img, (img.shape[1] // 2, img.shape[0] // 2), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))


def report(key, plan):
    bad = [(r['name'] or '?', r['area'], r['measured']) for r in plan['rooms_raw'] if abs(r['measured'] - r['area']) / max(r['area'], 1) > 0.08]
    nflat = len(plan['apartments'])
    nbox = len([f for f in plan['flats_raw'] if f.get('area')])
    sums = []
    for a in plan['apartments']:
        s = sum(r['area'] for r in a['rooms']) + sum(b['area'] for b in a['balconies'])
        sums.append((a['rooms_count'], a['area'], round(s, 2)))
    print(f'{key}: rooms {len(plan["rooms_raw"])}, flats {nflat}/{nbox} boxes, walls {len(plan["walls"])}, struct {len(plan["struct"])}, '
          f'windows {len(plan["windows"])}, swings {len(plan["swings"])}, lifts {len(plan["lifts"])}')
    print('   areas off by >8%:', bad)
    print('   flats (rooms, label area, sum of rooms):', sums)
    for m in plan['flat_match']:
        if m['colour_mismatch']:
            print('   colour mismatch:', m['rooms'], m['box'].get('area'))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    debug = '--check' in sys.argv
    keys = args or list(PLANS)
    only_furniture = '--furniture' in sys.argv   # the plans as they are, the furniture read again
    plans = json.load(open(OUT)) if os.path.exists(OUT) and (args or only_furniture) else {}
    for key in keys:
        if only_furniture:
            import furniture as FU
            sheet, block, _ = PLANS[key]
            pg = SH.doc()[SH.PAGES[sheet]]
            fr, _ = SH.fit(pg, block)
            FU.read(pg, fr, plans[key], Raster(pg, fr, CLIP[block]).rect)
            continue
        p = extract(key, debug)
        report(key, p)
        plans[key] = p
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(plans, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__':
    main()
