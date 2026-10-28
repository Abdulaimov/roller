"""Diagnostic: draw one category of vector paths of a plan PDF in its own colour.

    python inspect_pdf.py PLAN.pdf OUT.png x0 y0 x1 y1 [dpi]
"""
import sys
import fitz
from PIL import Image, ImageDraw

f, out = sys.argv[1], sys.argv[2]
x0, y0, x1, y1 = map(float, sys.argv[3:7])
dpi = float(sys.argv[7]) if len(sys.argv) > 7 else 300
k = dpi / 72
pg = fitz.open(f)[0]
W, H = int((x1 - x0) * k), int((y1 - y0) * k)
im = Image.new('RGB', (W, H), (255, 255, 255))
g = ImageDraw.Draw(im)
R = lambda c: tuple(round(v, 2) for v in c) if c is not None else None


def pts(d):
    out = []
    for it in d['items']:
        if it[0] == 're':
            r = it[1]
            out.append([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)])
        elif it[0] == 'qu':
            q = it[1]
            out.append([q.ul, q.ur, q.lr, q.ll])
        elif it[0] == 'l':
            out.append([it[1], it[2]])
        elif it[0] == 'c':
            out.append([it[1], it[4]])
    return [[((p[0] - x0) * k, (p[1] - y0) * k) for p in s] for s in out]

ROOMFILL = None
for d in pg.get_drawings():
    if not fitz.Rect(x0, y0, x1, y1).intersects(d['rect']):
        continue
    fill, col, w = R(d.get('fill')), R(d.get('color')), round(d.get('width') or 0, 2)
    for s in pts(d):
        if fill is not None and len(s) > 2:
            if fill in ((1.0, 1.0, 1.0),):
                continue
            c = tuple(int(v * 255) for v in fill)
            if fill == (0.0, 0.0, 0.0): c = (0, 0, 0)
            if fill in ((0.0, 0.0, 1.0), (0.0, 0.0, 0.72)): continue  # lettering
            g.polygon(s, fill=c)
        if col is not None:
            c = tuple(int(v * 255) for v in col)
            if col in ((0.0, 0.0, 0.72),): continue
            if col == (0.0, 0.0, 0.0) and w <= 0.12: c = (200, 200, 200)
            g.line(s + ([s[0]] if fill is not None else []), fill=c, width=max(1, int(w * k * 0.5)))
im.save(out)
print(out, W, H)
