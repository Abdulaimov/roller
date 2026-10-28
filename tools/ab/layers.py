"""Diagnostic: draw only the given stroke/fill colours of a plan PDF region, each in its own colour.

    python layers.py PLAN.pdf OUT.png x0 y0 x1 y1 dpi 'r,g,b[@w]' ...
A colour spec with @w matches strokes of that width; 'fill:r,g,b' matches fills.
"""
import sys
import fitz
from PIL import Image, ImageDraw

f, out = sys.argv[1], sys.argv[2]
x0, y0, x1, y1, dpi = map(float, sys.argv[3:8])
specs = sys.argv[8:]
PAL = [(220, 30, 30), (30, 120, 220), (20, 160, 60), (230, 130, 0), (150, 40, 200), (0, 170, 170), (120, 120, 120), (0, 0, 0)]
k = dpi / 72
pg = fitz.open(f)[0]
im = Image.new('RGB', (int((x1 - x0) * k), int((y1 - y0) * k)), (255, 255, 255))
g = ImageDraw.Draw(im)
R = lambda c: tuple(round(v, 2) for v in c) if c is not None else None
T = lambda p: ((p[0] - x0) * k, (p[1] - y0) * k)
clip = fitz.Rect(x0, y0, x1, y1)
for d in pg.get_drawings():
    if not clip.intersects(d['rect']):
        continue
    for i, s in enumerate(specs):
        fill = s.startswith('fill:')
        body = s[5:] if fill else s
        col, _, w = body.partition('@')
        col = tuple(float(v) for v in col.split(','))
        if fill:
            if R(d.get('fill')) != col:
                continue
            it = d['items']
            if len(it) == 2 and it[0][0] == 'l':
                g.polygon([T(it[0][1]), T(it[0][2]), T(it[1][2])], fill=PAL[i % len(PAL)])
            continue
        if R(d.get('color')) != col or (w and round(d.get('width') or 0, 2) != float(w)):
            continue
        for it in d['items']:
            if it[0] == 'l':
                g.line([T(it[1]), T(it[2])], fill=PAL[i % len(PAL)], width=2)
            elif it[0] == 'c':
                g.line([T(it[1]), T(it[2]), T(it[3]), T(it[4])], fill=PAL[i % len(PAL)], width=2)
            elif it[0] in ('re', 'qu'):
                q = it[1].quad if it[0] == 're' else it[1]
                g.polygon([T(q.ul), T(q.ur), T(q.lr), T(q.ll)], outline=PAL[i % len(PAL)], width=2)
im.save(out)
