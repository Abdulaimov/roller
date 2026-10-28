"""Furniture and sanitary blocks on the plan sheets.

The sheets are AutoCAD exports: every block (a bed, a sofa set, a bathtub...) is drawn as a run of
consecutive drawing commands (white fills cut into triangles, black outlines, details), so blocks
are found by drawing order: consecutive furniture-styled items whose extents touch belong together.

    tools/ab/py tools/ab/blocks.py KEY [OUT.png]   # inventory of the sheet's blocks
"""
import math
import os
import sys
from collections import Counter

from shapely.geometry import LineString, MultiPoint, Polygon, box

sys.path.insert(0, os.path.dirname(__file__))
import extract_plan as E  # noqa: E402

WHITE = (1.0, 1.0, 1.0)
BLACK = (0.0, 0.0, 0.0)
TAN = (0.65, 0.58, 0.4)          # sanitary ware
GREYS = {(0.41, 0.41, 0.41), (0.5, 0.5, 0.5)}


def style(d):
    return (d['type'], E.R2(d.get('color')), E.R2(d.get('fill')), round(d.get('width') or 0, 2))


def furniture_style(st):
    t, c, f, w = st
    if t == 'f':
        return 'fill' if f == WHITE else None
    if c == TAN:
        return 'tan'
    if c == BLACK and w in (0.06, 0.12, 0.54, 0.72):
        return f'k{int(round(w * 100)):02d}'
    return None


class Block:
    def __init__(self, i):
        self.i0 = self.i1 = i
        self.items = []      # (index, kind, [polyline, ...], has_curve)
        self.bb = None

    def add(self, i, kind, subs, curve, bb):
        self.items.append((i, kind, subs, curve))
        self.i1 = i
        self.bb = bb if self.bb is None else (min(self.bb[0], bb[0]), min(self.bb[1], bb[1]), max(self.bb[2], bb[2]), max(self.bb[3], bb[3]))

    @property
    def counts(self):
        return Counter(k for _, k, _, _ in self.items)

    def points(self, kinds=None):
        return [p for _, k, subs, _ in self.items if kinds is None or k in kinds for s in subs for p in s]

    def lines(self, kinds=None):
        return [LineString(s) for _, k, subs, _ in self.items if kinds is None or k in kinds for s in subs if len(s) >= 2]

    def fills(self):
        out = []
        for _, k, subs, _ in self.items:
            if k == 'fill':
                for s in subs:
                    if len(s) >= 3:
                        g = Polygon(s).buffer(0)
                        if g.area > 1e-6:
                            out.append(g)
        return out

    def obb(self, kinds=None):
        pts = self.points(kinds)
        r = MultiPoint(pts).minimum_rotated_rectangle
        if r.geom_type != 'Polygon':
            return None
        cs = list(r.exterior.coords)[:4]
        e1, e2 = math.dist(cs[0], cs[1]), math.dist(cs[1], cs[2])
        if e1 >= e2:
            u = ((cs[1][0] - cs[0][0]) / e1, (cs[1][1] - cs[0][1]) / e1)
        else:
            u = ((cs[2][0] - cs[1][0]) / e2, (cs[2][1] - cs[1][1]) / e2)
        c = r.centroid
        return dict(c=(c.x, c.y), L=max(e1, e2), W=min(e1, e2), u=u, poly=r)


def sheet_blocks(sh, region=None, gap=3, near=0.3):
    """the furniture blocks of a sheet (optionally only within region, plan metres)"""
    blocks, cur = [], None
    for i, d in enumerate(sh.drawings):
        kind = furniture_style(style(d))
        if kind is None:
            continue
        subs = [s for s in sh.path_points(d) if len(s) >= 2]
        if any(it[0] in ('re', 'qu') for it in d['items']):
            # rectangles come as their four corners: close them (a table, a car, a nightstand)
            subs = [s + [s[0]] if len(s) == 4 else s for s in subs]
        pts = [p for s in subs for p in s]
        if not pts:
            continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        bb = (min(xs), min(ys), max(xs), max(ys))
        if region is not None and not region.contains(box(*bb)):
            continue
        curve = any(it[0] == 'c' for it in d['items'])
        if cur is None or i - cur.i1 > gap or box(*cur.bb).buffer(near).disjoint(box(*bb)):
            cur = Block(i)
            blocks.append(cur)
        cur.add(i, kind, subs, curve, bb)
    return blocks


def signature(b):
    c = b.counts
    o = b.obb()
    dims = (round(o['L'], 1), round(o['W'], 1)) if o else (0, 0)
    return tuple(sorted(c.items())), dims


def main():
    key = sys.argv[1]
    sh = E.Sheet(key)
    blocks = sheet_blocks(sh)
    sig = Counter(signature(b) for b in blocks if len(b.items) >= 2)
    print(key, 'blocks', len(blocks), 'types', len(sig))
    for s, n in sig.most_common():
        print(f'{n:4d}  {s}')


if __name__ == '__main__':
    main()


def catalogue(key, out, per_type=1, px=120):
    """one picture per block type (signature), first instances, labelled"""
    from PIL import Image, ImageDraw, ImageFont
    sh = E.Sheet(key)
    blocks = [b for b in sheet_blocks(sh) if len(b.items) >= 2]
    by = {}
    for b in blocks:
        by.setdefault(signature(b), []).append(b)
    f = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 12)
    tiles = []
    for sig, bs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        for b in bs[:per_type]:
            x0, y0, x1, y1 = b.bb
            W, H = max(60, int((x1 - x0) * px) + 20), max(60, int((y1 - y0) * px) + 20)
            im = Image.new('RGB', (max(W, 260), H + 34), 'white')
            g = ImageDraw.Draw(im)
            T = lambda p: (10 + (p[0] - x0) * px, 10 + (y1 - p[1]) * px)
            for poly in b.fills():
                g.polygon([T(p) for p in poly.exterior.coords], fill=(215, 232, 250))
            col = {'tan': (160, 110, 30), 'k54': (0, 140, 0), 'k72': (0, 0, 0), 'k12': (200, 0, 160), 'k06': (90, 90, 90), 'grey': (0, 110, 220)}
            for _, k, subs, _ in b.items:
                if k == 'fill':
                    continue
                for s in subs:
                    g.line([T(p) for p in s], fill=col.get(k, (255, 0, 0)), width=1)
            txt = f"{len(bs)}x {dict(sig[0])} {sig[1]}"
            g.text((4, H + 4), txt[:60], fill=(0, 0, 0), font=f)
            g.text((4, H + 18), f'#{b.i0} at {b.bb[0]:.1f},{b.bb[1]:.1f}', fill=(90, 90, 90), font=f)
            tiles.append(im)
    # pack in rows
    Wmax = 1800
    rows, row, w = [], [], 0
    for t in tiles:
        if w + t.width > Wmax and row:
            rows.append(row)
            row, w = [], 0
        row.append(t)
        w += t.width + 8
    if row:
        rows.append(row)
    H = sum(max(t.height for t in r) + 8 for r in rows)
    sheet = Image.new('RGB', (Wmax, H), (235, 235, 235))
    y = 0
    for r in rows:
        x = 0
        for t in r:
            sheet.paste(t, (x, y))
            x += t.width + 8
        y += max(t.height for t in r) + 8
    sheet.save(out)
    print(out, sheet.size, len(tiles), 'types')
