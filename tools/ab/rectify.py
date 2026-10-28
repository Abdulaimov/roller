"""Unwrap one face of a block from a client render (or from a model shot taken with the same
camera) into a flat elevation in metres: plan x (or y) across, height up, with a metre grid. The
camera comes from tools/ab/calib.py; the face is the plan's facade line on one side.

    tools/ab/py tools/ab/rectify.py IMAGE.png KEY FACE CAM_JSON OUT.png [--px 12] [--z 0 82]

FACE: +y, -y, +x or -x (the plan side; for the slab blocks +y is the street side).
CAM_JSON: '{"pos": [...], "yaw": deg, "f": px, "v0": px, "size": [W, H]}'.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'blender'))
from ab.config import BLOCKS  # noqa: E402


def main():
    args = sys.argv[1:]
    opt = {}
    for k in ('--px', '--z'):
        if k in args:
            i = args.index(k)
            n = 2 if k == '--z' else 1
            opt[k] = [float(v) for v in args[i + 1:i + 1 + n]]
            del args[i:i + 1 + n]
    src, key, face, cam, out = args[:5]
    cam = json.loads(cam)
    px = opt.get('--px', [12])[0]
    z0, z1 = opt.get('--z', [0, 82])
    b = BLOCKS[key]
    plans = json.load(open(os.path.join(ROOT, 'blender', 'ab', 'plans.json')))
    enc = Polygon(plans[b['plans'][3]]['enclosure']).buffer(0)
    x0, y0, x1, y1 = enc.bounds
    a = math.radians(b['rot'])
    ca, sa = math.cos(a), math.sin(a)
    cx, cy = b['centre']
    # the face: across coordinate t (plan metres), fixed coordinate on the facade line
    if face in ('+y', '-y'):
        t0, t1, fixed = x0, x1, (y1 if face == '+y' else y0)
        pt = lambda t: (t, fixed)
    else:
        t0, t1, fixed = y0, y1, (x1 if face == '+x' else x0)
        pt = lambda t: (fixed, t)
    W = int((t1 - t0) * px)
    H = int((z1 - z0) * px)
    im = np.asarray(Image.open(src).convert('RGB')).astype(np.float32)
    iw, ih = cam['size']
    if im.shape[1] != iw:
        im = np.asarray(Image.open(src).convert('RGB').resize((iw, ih), Image.LANCZOS)).astype(np.float32)
    yaw = math.radians(cam['yaw'])
    fwd = np.array([math.sin(yaw), 0.0, -math.cos(yaw)])
    right = np.array([math.cos(yaw), 0.0, math.sin(yaw)])
    C = np.array(cam['pos'], float)
    ts = t0 + (np.arange(W) + 0.5) / px
    zs = z1 - (np.arange(H) + 0.5) / px
    TT, ZZ = np.meshgrid(ts, zs)
    PX, PY = np.vectorize(pt)(TT)
    SX = cx + ca * PX - sa * PY
    SY = cy + sa * PX + ca * PY
    P = np.stack([SX, ZZ, -SY], axis=-1) - C
    xc, yc, zc = P @ right, P[..., 1], P @ fwd
    u = iw / 2 + cam['f'] * xc / zc
    v = cam['v0'] - cam['f'] * yc / zc
    ok = (zc > 1) & (u >= 0) & (u < iw - 1) & (v >= 0) & (v < ih - 1)
    u = np.clip(u, 0, iw - 1.001)
    v = np.clip(v, 0, ih - 1.001)
    ui, vi = u.astype(int), v.astype(int)
    fu, fv = (u - ui)[..., None], (v - vi)[..., None]
    c = (im[vi, ui] * (1 - fu) * (1 - fv) + im[vi, ui + 1] * fu * (1 - fv) + im[vi + 1, ui] * (1 - fu) * fv + im[vi + 1, ui + 1] * fu * fv)
    c[~ok] = 255
    img = Image.fromarray(c.astype(np.uint8))
    g = ImageDraw.Draw(img)
    f = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 11)
    for m in range(math.ceil(t0), int(t1) + 1):
        X = (m - t0) * px
        g.line([(X, 0), (X, 6 if m % 5 else 14)], fill=(255, 0, 0))
        if m % 5 == 0:
            g.text((X + 2, 14), str(m), fill=(255, 0, 0), font=f)
    for m in range(math.ceil(z0), int(z1) + 1):
        Y = (z1 - m) * px
        g.line([(0, Y), (6 if m % 5 else 14, Y)], fill=(0, 0, 255))
        if m % 5 == 0:
            g.text((16, Y - 6), str(m), fill=(0, 0, 255), font=f)
    img.save(out)
    print(out, img.size, f'{t0:.1f}..{t1:.1f} m across, {z0}..{z1} m up')


if __name__ == '__main__':
    main()
