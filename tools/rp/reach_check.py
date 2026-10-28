"""Where the visitor can walk in a flat, from its entrance (the walk's collision lines, a 0.23 m
reach as in src/floor.js reachableRooms), room by room; with --draw, a picture over the sheet.

    node tools/ab/dump_walk.mjs build/rp/compare/walk.json B14-3 [...]
    tools/ab/py tools/rp/reach_check.py build/rp/compare/walk.json [--draw] [--furniture]
"""
import json
import os
import sys

import cv2
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet as SH  # noqa: E402
import extract as EX  # noqa: E402


def walkable(d, outline, furniture=True):
    segs = d['segments']
    if not furniture:
        # (the walls and doors only: the segments that are no edge of a piece of furniture)
        pts = {(round(p[0], 4), round(p[1], 4)) for o in d['obstacles'] if o['what'] not in ('door', 'door shut', 'front door') for p in o['poly']}
        segs = [s_ for s_ in segs if not ((round(s_[0], 4), round(s_[1], 4)) in pts and (round(s_[2], 4), round(s_[3], 4)) in pts)]
    blocked = unary_union([LineString([(s[0], s[1]), (s[2], s[3])]).buffer(0.23, quad_segs=3) for s in segs
                           if LineString([(s[0], s[1]), (s[2], s[3])]).distance(outline) < 1])
    free = outline.difference(blocked)
    start = Point(d['reach']['start'])
    parts = list(getattr(free, 'geoms', [free]))
    return min(parts, key=lambda g: g.distance(start))


def main():
    src = sys.argv[1]
    data = json.load(open(src))
    P = json.load(open(os.path.join(SH.ROOT, 'src', 'model', 'plans.json')))
    bad = 0
    for aid, d in data.items():
        outline = unary_union([Polygon(r['poly']).buffer(0.2, join_style=2) for r in d['rooms']]).buffer(-0.04, join_style=2)
        mine = walkable(d, outline, '--furniture' in sys.argv)
        lost = []
        for r in d['rooms']:
            rp = Polygon(r['poly']).buffer(0)
            share = rp.intersection(mine).area / max(rp.area, 1e-6)
            if share < 0.3 and r['kind'] not in ('loggia',) and r['area'] > 2.6:
                lost.append(f"{r['kind']} {r['area']} ({share:.0%})")
        bad += bool(lost)
        print(f"{aid}: {'all rooms reached' if not lost else 'not reached: ' + ', '.join(lost)}")
        if '--draw' in sys.argv:
            key = d['plan']
            sheet, block, _ = EX.PLANS[key]
            pg = SH.doc()[SH.PAGES[sheet]]
            fr, _ = SH.fit(pg, block)
            x0, y0, x1, y1 = outline.buffer(1.0).bounds
            sx0, sy1 = fr.to_sheet(x0, y0)
            sx1, sy0 = fr.to_sheet(x1, y1)
            dpi = 400
            k = 72 / dpi
            pix = pg.get_pixmap(dpi=dpi, clip=SH.pymupdf.Rect(sx0, sy0, sx1, sy1), alpha=False)
            img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3).copy()
            P2 = lambda X, Y: (int((fr.to_sheet(X, Y)[0] - sx0) / k), int((fr.to_sheet(X, Y)[1] - sy0) / k))
            ov = (img * 0.5 + 127).astype(np.uint8)
            lay = ov.copy()
            for g in getattr(mine, 'geoms', [mine]):
                cv2.fillPoly(lay, [np.array([P2(*p) for p in g.exterior.coords], np.int32)], (0, 220, 0))
            ov = cv2.addWeighted(lay, 0.35, ov, 0.65, 0)
            for s in d['segments']:
                cv2.line(ov, P2(s[0], s[1]), P2(s[2], s[3]), (230, 0, 0), 2)
            for o in d['obstacles']:
                if o['what'] in ('door', 'door shut', 'front door'):
                    cv2.polylines(ov, [np.array([P2(*p) for p in o['poly']], np.int32)], False, (0, 0, 255), 4)
            cv2.imwrite(os.path.join(os.path.dirname(src), f'{aid}_reach.png'), cv2.cvtColor(np.concatenate([img, ov], 1), cv2.COLOR_RGB2BGR))
    print(f'{len(data)} flats, {bad} with rooms the visitor cannot walk into')


if __name__ == '__main__':
    main()
