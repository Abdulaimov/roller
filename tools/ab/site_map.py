"""Site plan (genplan, 1:1000) -> ground classes and polygons in site metres.

    tools/ab/py tools/ab/site_map.py            # -> build/site_classes.png, build/site_raw.json

The genplan's areas (asphalt, paving, lawn, playgrounds...) are PDF patterns, not plain fills,
so they are read from a rendering at 10 px/m: every pixel is given the class of the nearest
palette colour, labels and lines are filled in from their surroundings, then each class is
traced into polygons. Site metres: x east (right on the sheet), y north (up), origin ORIGIN_PT.
"""
import json
import os
import sys

import cv2
import numpy as np
import pymupdf

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
GP = os.path.join(ROOT, '..', '00_Материалы_клиента', 'Генплан', 'ГП Али Бинокор.pdf')
M_PER_PT = 25.4 / 72          # 1:1000: one paper mm is one metre
CLIP = (150, 60, 1180, 720)    # sheet region of the site (pt)
ORIGIN_PT = (700.0, 430.0)     # site origin on the sheet (pt): middle of the plot
PX_PER_M = 10.0
DPI = int(PX_PER_M * 25.4)     # 254 dpi -> 10 px per metre

# palette (RGB) -> class
PALETTE = [
    ((123, 123, 124), 'asphalt'), ((89, 92, 87), 'asphalt'), ((157, 155, 151), 'asphalt'), ((105, 105, 105), 'asphalt'),
    ((68, 105, 43), 'lawn'), ((46, 57, 32), 'lawn'), ((90, 130, 60), 'lawn'), ((35, 45, 25), 'lawn'),
    ((218, 204, 191), 'paving'), ((192, 184, 178), 'paving'), ((234, 231, 235), 'paving'), ((205, 192, 175), 'paving'),
    ((162, 15, 3), 'building'), ((140, 10, 5), 'building'),
    ((221, 138, 127), 'podium'), ((164, 71, 75), 'podium'), ((200, 120, 110), 'podium'),
    ((242, 175, 62), 'play'), ((247, 224, 70), 'play'), ((253, 110, 60), 'play'), ((250, 150, 50), 'play'),
    ((242, 54, 146), 'kindergarten'), ((250, 120, 190), 'kindergarten'),
    ((71, 68, 243), 'blue'), ((139, 141, 234), 'blue'), ((90, 90, 245), 'blue'),
    ((255, 255, 255), 'white'),
]
CLASSES = ['white', 'asphalt', 'lawn', 'paving', 'building', 'podium', 'play', 'kindergarten', 'blue', 'sport']
DEBUG = {'white': (255, 255, 255), 'asphalt': (110, 110, 112), 'lawn': (70, 120, 50), 'paving': (215, 200, 180),
         'building': (150, 20, 20), 'podium': (220, 140, 130), 'play': (245, 160, 50), 'kindergarten': (240, 60, 150),
         'blue': (60, 60, 240), 'sport': (40, 200, 60)}


def render():
    pg = pymupdf.open(GP)[0]
    pix = pg.get_pixmap(dpi=DPI, clip=pymupdf.Rect(*CLIP))
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    return a.copy()


def classify(img):
    h, w, _ = img.shape
    pal = np.array([c for c, _ in PALETTE], np.float32)
    cls_of = np.array([CLASSES.index(n) for _, n in PALETTE])
    X = img.reshape(-1, 3).astype(np.float32)
    lab = np.empty(len(X), np.int32)
    dist = np.empty(len(X), np.float32)
    for i in range(0, len(X), 2_000_000):
        d = ((X[i:i + 2_000_000, None, :] - pal[None]) ** 2).sum(-1)
        k = d.argmin(1)
        lab[i:i + 2_000_000] = cls_of[k]
        dist[i:i + 2_000_000] = np.sqrt(d[np.arange(len(k)), k])
    lab = lab.reshape(h, w)
    dist = dist.reshape(h, w)
    # the football pitch: saturated mid green with light stripes
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    sport = (hsv[..., 0] > 35) & (hsv[..., 0] < 75) & (hsv[..., 1] > 120) & (hsv[..., 2] > 120)
    sport = cv2.morphologyEx(sport.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    sport = cv2.morphologyEx(sport, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8)).astype(bool)
    lab[sport] = CLASSES.index('sport')
    unknown = (dist > 38) & ~sport
    # dark lines, lettering, red/blue lines: unknown, filled in from the neighbours below
    dark = img.max(-1) < 40
    redline = (img[..., 0] > 200) & (img[..., 1] < 60) & (img[..., 2] < 60)
    unknown |= dark | redline
    # small white islands inside the site are label boxes and lane markings, not empty ground
    white = ((lab == CLASSES.index('white')) & ~unknown).astype(np.uint8)
    n, cc, stats, _ = cv2.connectedComponentsWithStats(white, 8)
    small = stats[:, cv2.CC_STAT_AREA] < 400 * PX_PER_M * PX_PER_M
    small[0] = False
    # the whole box (with the lettering inside it), not only its white
    boxes = np.zeros_like(white)
    for i in np.nonzero(small)[0]:
        x, y, w, h = stats[i, :4]
        sub = (cc[y:y + h, x:x + w] == i).astype(np.uint8)
        pts = cv2.findNonZero(sub)
        if pts is None:
            continue
        r = cv2.minAreaRect(pts + np.array([x, y]))
        cv2.fillPoly(boxes, [cv2.boxPoints(r).astype(np.int32)], 1)
    unknown |= cv2.dilate(boxes, np.ones((5, 5), np.uint8)).astype(bool)
    return lab, unknown


def fill_unknown(lab, unknown):
    """Give every unknown pixel the class of the nearest known one, then a majority filter."""
    known = (~unknown).astype(np.uint8)
    # distance transform with labels: nearest known pixel
    d, idx = cv2.distanceTransformWithLabels(1 - known, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(known)
    table = np.zeros(idx.max() + 1, np.int32)
    table[idx[ys, xs]] = lab[ys, xs]
    out = table[idx]
    # majority (mode) filter: 7x7, per class
    votes = np.stack([cv2.boxFilter((out == c).astype(np.float32), -1, (7, 7)) for c in range(len(CLASSES))])
    return votes.argmax(0)


def trace(lab):
    """Polygons per class (outer rings with holes), in site metres."""
    s = 1.0 / PX_PER_M
    ox_pt, oy_pt = CLIP[0], CLIP[1]

    def to_site(c):
        px = ox_pt + (c[0] + 0.5) * s / M_PER_PT
        py = oy_pt + (c[1] + 0.5) * s / M_PER_PT
        return [round((px - ORIGIN_PT[0]) * M_PER_PT, 2), round(-(py - ORIGIN_PT[1]) * M_PER_PT, 2)]

    out = {}
    for ci, name in enumerate(CLASSES):
        if name == 'white':
            continue
        m = (lab == ci).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        polys = []
        if hier is None:
            out[name] = polys
            continue
        hier = hier[0]
        for i, c in enumerate(cs):
            if hier[i][3] != -1:
                continue  # a hole: attached to its parent below
            if cv2.contourArea(c) < 4 * PX_PER_M * PX_PER_M:  # < 4 m2
                continue
            ring = cv2.approxPolyDP(c, 1.2, True)[:, 0, :]
            holes = []
            j = hier[i][2]
            while j != -1:
                if cv2.contourArea(cs[j]) >= 2 * PX_PER_M * PX_PER_M:
                    holes.append([to_site(p) for p in cv2.approxPolyDP(cs[j], 1.2, True)[:, 0, :]])
                j = hier[j][0]
            polys.append(dict(ring=[to_site(p) for p in ring], holes=holes))
        out[name] = polys
    return out


def marks():
    """Tree symbols (one small picture placed ~100 times), zone numbers of the legend (8 parking,
    3 playground, 14 sports ground, 11 car park ramp...) and the plot boundary, in site metres."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union
    pg = pymupdf.open(GP)[0]
    site = lambda x, y: [round((x - ORIGIN_PT[0]) * M_PER_PT, 2), round(-(y - ORIGIN_PT[1]) * M_PER_PT, 2)]
    trees = []
    for img in pg.get_images(full=True):
        rects = pg.get_image_rects(img[0])
        if len(rects) > 30:  # the tree symbol
            trees += [site((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2) for r in rects]
    words = []
    clip = pymupdf.Rect(*CLIP)
    for w in pg.get_text('words', clip=clip):
        if w[4] in ('2', '3', '4', '5', '6', '7', '8', '11', '13', '14', 'ПС'):
            words.append(dict(t=w[4], p=site((w[0] + w[2]) / 2, (w[1] + w[3]) / 2), h=round((w[3] - w[1]) * M_PER_PT, 2)))
    segs = []
    for d in pg.get_drawings():
        c = d.get('color')
        if c is None or tuple(round(v, 2) for v in c) != (1.0, 0.0, 0.0) or abs((d.get('width') or 0) - 1.98) > 0.05:
            continue
        segs += [LineString([site(it[1].x, it[1].y), site(it[2].x, it[2].y)]) for it in d['items'] if it[0] == 'l']
    u = unary_union([q.buffer(1.6) for q in segs])
    holes = [Polygon(r) for g in getattr(u, 'geoms', [u]) for r in g.interiors]
    plot = max(holes, key=lambda p: p.area).buffer(1.6).simplify(0.5)
    # buildings drawn as plain fills: the kindergarten's three wings (pink), the hospital (blue)
    fills = {}
    for d in pg.get_drawings():
        f = d.get('fill')
        if f is None:
            continue
        k = tuple(round(v, 2) for v in f)
        if k not in ((1.0, 0.25, 0.63), (0.33, 0.33, 1.0)):
            continue
        pts = [site(it[1].x, it[1].y) for it in d['items'] if it[0] == 'l']
        if d['items'] and d['items'][-1][0] == 'l':
            pts.append(site(d['items'][-1][2].x, d['items'][-1][2].y))
        if len(pts) >= 3:
            g = Polygon(pts).buffer(0)
            if g.area > 0:
                fills.setdefault(k, []).append(g)
    def comps(k, min_area):
        u = unary_union([g.buffer(0.02) for g in fills.get(k, [])])
        return [[[round(x, 2), round(y, 2)] for x, y in g.simplify(0.2).exterior.coords]
                for g in getattr(u, 'geoms', [u]) if g.area > min_area]
    return dict(trees=trees, words=words, plot=[[round(x, 2), round(y, 2)] for x, y in plot.exterior.coords],
                kinder=comps((1.0, 0.25, 0.63), 150), blue=comps((0.33, 0.33, 1.0), 300))


def main():
    os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
    img = render()
    lab, unknown = classify(img)
    lab = fill_unknown(lab, unknown)
    dbg = np.zeros(img.shape, np.uint8)
    for ci, name in enumerate(CLASSES):
        dbg[lab == ci] = DEBUG[name]
    cv2.imwrite(os.path.join(ROOT, 'build', 'site_classes.png'), dbg[:, :, ::-1])
    cv2.imwrite(os.path.join(ROOT, 'build', 'site_classes_small.png'), cv2.resize(dbg[:, :, ::-1], None, fx=0.3, fy=0.3, interpolation=cv2.INTER_NEAREST))
    np.save(os.path.join(ROOT, 'build', 'site_labels.npy'), lab.astype(np.uint8))
    polys = trace(lab)
    json.dump(dict(origin_pt=ORIGIN_PT, m_per_pt=M_PER_PT, classes=polys, **marks()), open(os.path.join(ROOT, 'build', 'site_raw.json'), 'w'))
    for k, v in polys.items():
        print(k, len(v))


if __name__ == '__main__':
    main()
