"""The shop signs of the client's renders (1, 3, 6): white letters on dark panels over the shop
windows of the podium's two street faces - CHANEL, LOUIS VUITTON, DIOR, MUDO and PARKING along
кӯчаи И. Нарзиқулова (blocks В and Б), ZARA, CONCEPT and LACOSTA (spelled so on render 6) along
кӯчаи Ш. Ҳусейнзода (blocks Б and А). Draws the artwork into public/signs/ and writes
public/signs/signs.json (src/signs.js lays them over the model; no rebuild of the scene).

    tools/ab/py tools/rp/signs.py
"""
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Point, Polygon

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'public', 'signs')
ROT = -49.5   # the sheet's frame on the ground (blender/rp/config.py)
FONT = '/System/Library/Fonts/HelveticaNeue.ttc'

# (name, face, where along the face 0..1 from block Б's street corner, the span it may take, m);
# on the east face the place is the sheet's y instead: render 6 has LACOSTA on Б's shop front just
# short of the step out to block А, CONCEPT and then ZARA (further from the corner) on А's (28.10.2026:
# they were all three on А's, in the reverse order - Б's front stands 4 m back and was not found)
SIGNS = [
    ('CHANEL', 'north', 0.10, 6.0), ('LOUIS VUITTON', 'north', 0.26, 7.0), ('DIOR', 'north', 0.42, 5.0),
    ('MUDO', 'north', 0.62, 5.0), ('PARKING', 'north', 0.86, 5.0),
    ('LACOSTA', 'east', -11.5, 6.0), ('CONCEPT', 'east', -23.5, 6.0), ('ZARA', 'east', -28.5, 5.0),
]
Z, H = 4.05, 0.62   # the middle of the sign over the ground floor's windows (4.5 m floor), its height


def rot(x, y, deg):
    a = math.radians(deg)
    return (math.cos(a) * x - math.sin(a) * y, math.sin(a) * x + math.cos(a) * y)


def artwork(name):
    """white letters on a dark panel, the panel a little wider than the word"""
    fnt = ImageFont.truetype(FONT, 150, index=1)   # (Helvetica Neue Bold)
    l, t, r, b = fnt.getbbox(name)
    track = 18 * (len(name) - 1)
    w, h = int(r - l + track + 220), 300
    im = Image.new('RGBA', (w, h), (38, 42, 47, 255))
    d = ImageDraw.Draw(im)
    x = 110
    for ch in name:
        cl, ct, cr, cb = fnt.getbbox(ch)
        d.text((x - cl, (h - (b - t)) / 2 - t), ch, font=fnt, fill=(255, 255, 255, 255))
        x += (cr - cl if ch != ' ' else fnt.getlength(' ')) + 18
    path = os.path.join(OUT, name.lower().replace(' ', '_') + '.png')
    im.save(path)
    return os.path.basename(path)


def main():
    os.makedirs(OUT, exist_ok=True)
    cx = json.load(open(os.path.join(ROOT, 'src', 'model', 'complex.json')))
    site = Polygon(cx['podium']).buffer(0)
    sheet = Polygon([rot(x, y, -ROT) for x, y in site.exterior.coords])
    x0, y0, x1, y1 = sheet.bounds
    # the street faces in the sheet's frame: along Нарзиқулова at the top (y = y1), along Ҳусейнзода
    # on the right (x = x1); each from the street corner (block Б) away from it
    faces = {}
    for key, line in (('north', LineString([(x1, y1), (x0, y1)])), ('east', LineString([(x1, y1), (x1, y0)]))):
        # the stretch of the line the podium's face runs along (within 3 m: it steps back here and
        # there; the corner is cut)
        hits = [k / 4 for k in range(int(line.length * 4)) if sheet.exterior.distance(line.interpolate(k / 4)) <= 3.0]
        faces[key] = (line, hits[0], hits[-1])
    out = []
    for name, face, at, span in SIGNS:
        line, s0, s1 = faces[face]
        u = ((line.coords[1][0] - line.coords[0][0]) / line.length, (line.coords[1][1] - line.coords[0][1]) / line.length)
        n = (0.0, 1.0) if face == 'north' else (1.0, 0.0)
        m = line.interpolate(s0 + at * (s1 - s0)) if face == 'north' else Point(x1, at)
        # onto the podium's own face there: in from the line until the wall is met
        d = 0.0
        while d < 8 and not sheet.contains(Point(m.x - n[0] * (d + 0.05), m.y - n[1] * (d + 0.05))):
            d += 0.05
        mid = (m.x - n[0] * d, m.y - n[1] * d)
        a = (mid[0] - u[0] * span / 2 + n[0] * 0.15, mid[1] - u[1] * span / 2 + n[1] * 0.15)
        b = (mid[0] + u[0] * span / 2 + n[0] * 0.15, mid[1] + u[1] * span / 2 + n[1] * 0.15)
        # (the sign reads from the street: left to right as one faces the face)
        if u[0] * -n[1] + u[1] * n[0] < 0:
            a, b = b, a
        A, B, N = rot(*a, ROT), rot(*b, ROT), rot(*n, ROT)
        out.append(dict(file=artwork(name), a=[round(v, 3) for v in A], b=[round(v, 3) for v in B],
                        n=[round(v, 4) for v in N], z=Z, h=H, margin=0.2, kind='sign'))
        print(f'{name:14s} {face}: {at:.2f}, {d:.2f} m in from the line, sheet ({mid[0]:.1f}, {mid[1]:.1f})')
    json.dump(dict(set='regnum', sets=dict(regnum=out)), open(os.path.join(OUT, 'signs.json'), 'w'), indent=1)
    print('wrote', len(out), 'signs')


if __name__ == '__main__':
    main()
