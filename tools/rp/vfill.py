"""The room fills of a sheet as vector polygons, in plan metres of a block: each fill colour's
pieces joined (the sheets' hatches come cut into strips). For tools/rp/extract.py."""
import os
import sys

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet as SH  # noqa: E402


def subpaths(d):
    """the closed outlines of a fill drawing (lines, rectangles, quads; curves flattened)"""
    out, cur = [], []
    for it in d['items']:
        k = it[0]
        if k == 'l':
            if cur and (abs(cur[-1].x - it[1].x) > 0.01 or abs(cur[-1].y - it[1].y) > 0.01):
                out.append(cur)
                cur = []
            if not cur:
                cur = [it[1]]
            cur.append(it[2])
        elif k == 'c':
            if not cur:
                cur = [it[1]]
            b = it[1:5]
            for i in range(1, 9):
                t = i / 8
                w = ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3)
                cur.append(SH.pymupdf.Point(sum(a * q.x for a, q in zip(w, b)), sum(a * q.y for a, q in zip(w, b))))
        elif k == 're':
            if cur:
                out.append(cur)
                cur = []
            r = it[1]
            out.append([r.tl, r.tr, r.br, r.bl])
        elif k == 'qu':
            if cur:
                out.append(cur)
                cur = []
            q = it[1]
            out.append([q.ul, q.ur, q.lr, q.ll])
    if cur:
        out.append(cur)
    return out


def fills(pg, fr, rect):
    """{colour (0-255 rgb): polygon} of the light fills inside rect (the room and balcony fills)"""
    by = {}
    for d in pg.get_drawings():
        if not d.get('fill') or not rect.intersects(d['rect']):
            continue
        col = tuple(int(round(c * 255)) for c in d['fill'])
        if min(col) < 90 or max(col) < 170:
            continue   # (dark fills: walls, symbols)
        for sp in subpaths(d):
            if len(sp) < 3:
                continue
            g = Polygon([fr.to_plan(p.x, p.y) for p in sp]).buffer(0)
            if not g.is_empty:
                by.setdefault(col, []).append(g)
    clip = box(*[*fr.to_plan(rect.x0, rect.y1), *fr.to_plan(rect.x1, rect.y0)])
    # (pieces of one hatch a few millimetres apart - cut along an axis line - are one floor; the
    # walls between rooms are 8 cm and more)
    return {c: unary_union(gs).buffer(0.015, join_style=2).buffer(-0.015, join_style=2).intersection(clip) for c, gs in by.items()}
