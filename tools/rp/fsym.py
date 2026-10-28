"""Furniture symbols on a plan sheet: the thin black strokes (furniture, sanitary ware, counters)
joined into connected drawings, in plan metres of the block (tools/rp/furniture.py classifies them)."""
import math
import os
import sys

import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet as SH  # noqa: E402


def segments(pg, fr, rect):
    out = []
    for d in pg.get_drawings():
        if not rect.contains(d['rect']) or not d.get('color') or d.get('fill'):
            continue
        if max(d['color']) > 0.05 or (d.get('width') or 0) > 0.75:
            continue
        for it in d['items']:
            k = it[0]
            if k == 'l':
                pts = [it[1], it[2]]
            elif k == 'c':
                b = it[1:5]
                pts = []
                for i in range(9):
                    t = i / 8
                    w = ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3)
                    pts.append(SH.pymupdf.Point(sum(a * q.x for a, q in zip(w, b)), sum(a * q.y for a, q in zip(w, b))))
            elif k in ('re', 'qu'):
                q = it[1].quad if k == 're' else it[1]
                pts = [q.ul, q.ur, q.lr, q.ll, q.ul]
            else:
                continue
            P = [fr.to_plan(p.x, p.y) for p in pts]
            ln = LineString(P)
            if ln.length > 1e-3:
                out.append((ln, k == 'c', d.get('width') or 0))
    return out


def components(segs, gap=0.025):
    """connected drawings: lines that touch (within gap) are one symbol"""
    lines = [s[0] for s in segs]
    blobs = unary_union([ln.buffer(gap, quad_segs=2) for ln in lines])
    blobs = list(getattr(blobs, 'geoms', [blobs]))
    tree = shapely.STRtree(blobs)
    groups = [[] for _ in blobs]
    for s in segs:
        hits = tree.query(s[0].interpolate(0.5, normalized=True), predicate='intersects')
        if len(hits):
            groups[hits[0]].append(s)
    out = []
    for g in groups:
        if not g:
            continue
        geom = unary_union([s[0] for s in g])
        faces = list(polygonize(geom))
        shape = unary_union(faces) if faces else geom.convex_hull
        out.append(dict(segs=g, geom=geom, faces=faces, shape=shape, curves=sum(1 for s in g if s[1]),
                        thick=sum(1 for s in g if s[2] > 0.6)))
    return out


def mrr(g):
    """min rotated rect: centre, w (short), l (long), angle of the long side"""
    r = g.minimum_rotated_rectangle
    if r.geom_type != 'Polygon':
        b = g.bounds
        return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), 0.0, max(b[2] - b[0], b[3] - b[1]), 0.0
    c = list(r.exterior.coords)[:4]
    e1 = (c[1][0] - c[0][0], c[1][1] - c[0][1])
    e2 = (c[2][0] - c[1][0], c[2][1] - c[1][1])
    l1, l2 = math.hypot(*e1), math.hypot(*e2)
    if l1 < l2:
        e1, e2, l1, l2 = e2, e1, l2, l1
    a = math.atan2(e1[1], e1[0])
    # snap to the plan axes (the sheets are orthogonal)
    for s in (0, math.pi / 2, math.pi, -math.pi / 2, -math.pi):
        if abs(a - s) < math.radians(4):
            a = s
    ct = r.centroid
    return (ct.x, ct.y), l2, l1, a


def rects(pg, fr, rect):
    """closed four-sided outlines drawn as one path (AutoCAD rectangles and boxes): (polygon, thick,
    has_curves_in_path)"""
    out = []
    for d in pg.get_drawings():
        if not rect.contains(d['rect']) or not d.get('color') or d.get('fill'):
            continue
        if max(d['color']) > 0.05 or (d.get('width') or 0) > 0.75:
            continue
        thick = (d.get('width') or 0) > 0.6
        sub, cur = [], []
        for it in d['items']:
            if it[0] in ('re', 'qu'):
                q = it[1].quad if it[0] == 're' else it[1]
                sub.append([q.ul, q.ur, q.lr, q.ll])
                continue
            if it[0] != 'l':
                if cur:
                    sub.append(cur)
                cur = []
                continue
            a, b = it[1], it[2]
            if cur and (abs(cur[-1].x - a.x) > 0.05 or abs(cur[-1].y - a.y) > 0.05):
                sub.append(cur)
                cur = []
            if not cur:
                cur = [a]
            cur.append(b)
        if cur:
            sub.append(cur)
        for s in sub:
            P = [fr.to_plan(p.x, p.y) for p in s]
            if len(P) > 4 and math.dist(P[0], P[-1]) < 0.02:
                P = P[:-1]
            if len(P) != 4:
                continue
            g = Polygon(P)
            if not g.is_valid or g.area < 0.02:
                continue
            c, w, l, a = mrr(g)
            if g.area / max(w * l, 1e-6) > 0.92:
                out.append(dict(poly=g, c=c, w=w, l=l, a=a, thick=thick))
    return out
