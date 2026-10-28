"""A flat as the site builds it, drawn over its sales-book sheet: the sheet faded, our walls (grey),
the collision lines of the walk (red), door leaves (green, shut ones dark), furniture (orange),
doorways (cyan), room outlines (blue). For checking a flat by eye against the drawing.

    node tools/ab/dump_walk.mjs build/rp/compare/walk.json B14-3 [...]   # (site on 5197)
    tools/ab/py tools/rp/compare.py build/rp/compare/walk.json           # -> build/rp/compare/<id>.png
"""
import json
import os
import sys

import cv2
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet as SH  # noqa: E402
import extract as EX  # noqa: E402


def main():
    src = sys.argv[1]
    data = json.load(open(src))
    P = json.load(open(os.path.join(SH.ROOT, 'blender', 'rp', 'plans.json')))
    doc = SH.doc()
    out_dir = os.path.dirname(src)
    for aid, d in data.items():
        key = d['plan']
        plan = P[key]
        sheet, block, _ = EX.PLANS[key]
        pg = doc[SH.PAGES[sheet]]
        fr, _ = SH.fit(pg, block)
        g = unary_union([Polygon(r['poly']).buffer(0) for r in d['rooms']])
        x0, y0, x1, y1 = g.buffer(1.0).bounds
        sx0, sy1 = fr.to_sheet(x0, y0)
        sx1, sy0 = fr.to_sheet(x1, y1)
        dpi = 400
        pix = pg.get_pixmap(dpi=dpi, clip=SH.pymupdf.Rect(sx0, sy0, sx1, sy1), alpha=False)
        img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3).copy()
        sheet_img = img.copy()
        k = 72 / dpi
        big = 1

        def P2(X, Y):
            x, y = fr.to_sheet(X, Y)
            return (int(round((x - sx0) / k * big)), int(round((y - sy0) / k * big)))

        over = (img * 0.55 + 255 * 0.45).astype(np.uint8)
        layer = over.copy()
        for w in plan['walls'] + plan['struct']:
            cv2.fillPoly(layer, [np.array([P2(*p) for p in w], np.int32)], (120, 120, 120))
        over = cv2.addWeighted(layer, 0.45, over, 0.55, 0)
        for r in d['rooms']:
            cv2.polylines(over, [np.array([P2(*p) for p in r['poly']], np.int32)], True, (40, 90, 230), 1)
        for s in d['segments']:
            cv2.line(over, P2(s[0], s[1]), P2(s[2], s[3]), (230, 30, 30), 1)
        for o in d['obstacles']:
            pts = np.array([P2(*p) for p in o['poly']], np.int32)
            if o['what'] in ('door', 'door shut', 'front door'):
                cv2.polylines(over, [pts], False, (0, 150, 0) if o['what'] == 'door' else (0, 70, 0), 3)
            elif len(o['poly']) >= 3:
                cv2.polylines(over, [pts], True, (255, 140, 0), 2)
                c = pts.mean(axis=0).astype(int)
                cv2.putText(over, o['what'][:6], (int(c[0]) - 15, int(c[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 90, 0), 1)
        for dw in d['doorways']:
            cv2.line(over, P2(*dw['a']), P2(*dw['b']), (0, 200, 220), 3)
        both = np.concatenate([sheet_img, over], axis=1)
        path = os.path.join(out_dir, f'{aid}.png')
        cv2.imwrite(path, cv2.cvtColor(both, cv2.COLOR_RGB2BGR))
        print(path, both.shape)


if __name__ == '__main__':
    main()
