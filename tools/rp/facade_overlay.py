"""The sheets' facade drawn over a client render with its fitted camera (tools/rp/cameras.json):
every window, glazing and loggia of every floor, as a line at the height of its middle, coloured by
the face it is on and labelled with its plan, kind and index - to read off the render, window by
window, what each one is there (dark glass strip, punched window in the white grid, balcony).

    tools/ab/py tools/rp/facade_overlay.py render1 OUT.jpg [--blocks A,B] [--faces +x,+y] [--every 3]
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from calib import basis, to_scene  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, 'blender'))
from rp.config import level, plans_for, BLOCKS  # noqa: E402

RENDERS = os.path.join(ROOT, '..', '00_Материалы_клиента', 'Рендеры')
COL = {'+x': (255, 60, 60), '+y': (60, 220, 60), '-x': (60, 140, 255), '-y': (255, 200, 0)}


def face_of(bounds, c):
    x0, y0, x1, y1 = bounds
    d = {'+x': x1 - c[0], '-x': c[0] - x0, '+y': y1 - c[1], '-y': c[1] - y0}
    return min(d, key=d.get)


def projector(cam):
    W, H = cam['size']
    pos = np.array(cam['pos'])
    if cam['model'] == 'level':
        fwd, right, up = basis(math.radians(cam['yaw']), 0.0)
        f, v0 = cam['f'], cam['v0']

        def proj(P):
            d = P - pos
            zc = d @ fwd
            return (W / 2 + f * (d @ right) / zc, v0 - f * d[1] / zc) if zc > 1 else None
        return proj
    if cam['model'] == 'pinhole':
        fwd, right, up = basis(math.radians(cam['yaw']), math.radians(cam['pitch']))
        f = cam['f']

        def proj(P):
            d = P - pos
            zc = d @ fwd
            return (W / 2 + f * (d @ right) / zc, H / 2 - f * (d @ up) / zc) if zc > 1 else None
        return proj
    raise SystemExit('only fitted cameras (level, pinhole)')


def main():
    name, out = sys.argv[1], sys.argv[2]
    opt = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
    blocks = opt('--blocks', 'A,B,V').split(',')
    faces = opt('--faces', '+x,+y,-x,-y').split(',')
    every = int(opt('--every', '4'))
    cam = json.load(open(os.path.join(HERE, 'cameras.json')))[name]
    plans = json.load(open(os.path.join(ROOT, 'blender', 'rp', 'plans.json')))
    centres = json.load(open(os.path.join(ROOT, 'blender', 'rp', 'frame.json')))['centres']
    W, H = cam['size']
    im = Image.open(os.path.join(RENDERS, f'render_{name[-1]}.jpg')).convert('RGB').resize((W, H), Image.LANCZOS)
    im = Image.blend(im, Image.new('RGB', im.size, (0, 0, 0)), 0.25)
    d = ImageDraw.Draw(im)
    fnt = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 9)
    proj = projector(cam)
    # (only the faces turned to the camera: the overlay has no occlusion otherwise)
    a = math.radians(49.5)
    sx, sy = cam['pos'][0], -cam['pos'][2]
    cam_sheet = (math.cos(a) * sx - math.sin(a) * sy, math.sin(a) * sx + math.cos(a) * sy)
    NORMAL = {'+x': (1, 0), '-x': (-1, 0), '+y': (0, 1), '-y': (0, -1)}
    for key in blocks:
        cx, cy = centres[key]
        top = BLOCKS[key]['floors']
        pf = plans_for(key)
        for f in range(3, top + 1):
            if f % every and f not in (3, top):
                continue
            pk = pf[f]
            p = plans[pk]
            enc = Polygon(p['enclosure']).buffer(0)
            b, rim = enc.bounds, enc.exterior
            z = level(f) + 1.6
            items = [('w', i, q) for i, q in enumerate(p['windows'])] + [('g', i, q) for i, q in enumerate(p['glazing'])]
            for kind, i, q in items:
                g = Polygon(q).buffer(0)
                if g.distance(rim) > 0.7:
                    continue
                c = g.centroid
                face = face_of(b, (c.x, c.y))
                if face not in faces:
                    continue
                nx, ny = NORMAL[face]
                if (cam_sheet[0] - (cx + c.x)) * nx + (cam_sheet[1] - (cy + c.y)) * ny <= 0:
                    continue
                r = g.minimum_rotated_rectangle
                cs = list(r.exterior.coords)
                e = max([(cs[0], cs[1]), (cs[1], cs[2])], key=lambda s: math.dist(*s))
                (ax, ay), (bx, by) = e
                ox, oy = c.x - (ax + bx) / 2, c.y - (ay + by) / 2
                A = proj(to_scene((cx + ax + ox, cy + ay + oy), z))
                B = proj(to_scene((cx + bx + ox, cy + by + oy), z))
                if not A or not B:
                    continue
                col = COL[face] if kind == 'w' else tuple(min(255, v + 80) for v in COL[face])
                d.line([A, B], fill=col, width=3 if kind == 'w' else 2)
                if f in (3, top) or f % (every * 3) == 0:
                    d.text(((A[0] + B[0]) / 2 - 8, (A[1] + B[1]) / 2 - 11), f'{key}{kind}{i}', fill=col, font=fnt)
    im.save(out, quality=92)
    print(out, im.size)


if __name__ == '__main__':
    main()
