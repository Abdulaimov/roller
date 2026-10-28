"""Unwrap a picture onto one face of a block: every pixel goes to the place on the model it shows
(tools/ab/posmap.mjs: the model drawn from the same camera). The result is the face as an
elevation in plan metres, seen from outside, with a metre grid: what the render shows on that
face, on the model's own geometry (its jogs and chamfered corners included).

    tools/ab/py tools/ab/unwrap.py IMAGE POSMAP.f32 KEY FACE OUT.png [--px 20] [--z Z0 Z1] [--from F0 --to F1]

FACE: py, my, px, mx (plan side +y, -y, +x, -x). The picture is resized to the posmap's size first.
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'blender'))
from ab.config import BLOCKS  # noqa: E402


def plan_coords(key, P):
    """scene positions (x east, y up, z south) -> plan x, plan y, height"""
    b = BLOCKS[key]
    a = math.radians(b['rot'])
    ca, sa = math.cos(a), math.sin(a)
    cx, cy = b['centre']
    sx, sy = P[..., 0] - cx, -P[..., 2] - cy
    return ca * sx + sa * sy, -sa * sx + ca * sy, P[..., 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('image')
    ap.add_argument('posmap')
    ap.add_argument('key')
    ap.add_argument('face')
    ap.add_argument('out')
    ap.add_argument('--px', type=float, default=20)
    ap.add_argument('--z', nargs=2, type=float, default=None)
    ap.add_argument('--depth', type=float, default=6.0, help='how deep behind the face line a point may lie')
    ap.add_argument('--size', nargs=2, type=int, default=None)
    a = ap.parse_args()
    raw = np.fromfile(a.posmap, dtype=np.float32)
    if a.size:
        W, H = a.size
    else:
        W, H = 1600, raw.size // 4 // 1600
    pos = raw.reshape(H, W, 4)
    img = np.asarray(Image.open(a.image).convert('RGB').resize((W, H), Image.LANCZOS)).astype(np.float32)
    hit = pos[..., 3] > 0.5
    x, y, z = plan_coords(a.key, pos)
    plans = json.load(open(os.path.join(ROOT, 'blender', 'ab', 'plans.json')))
    b = BLOCKS[a.key]
    from shapely.geometry import Polygon
    enc = Polygon(plans[b['plans'][3]]['enclosure']).buffer(0)
    x0, y0, x1, y1 = enc.bounds
    face = {'py': '+y', 'my': '-y', 'px': '+x', 'mx': '-x'}.get(a.face, a.face)
    # t: along the face as seen from outside (left to right), d: how far behind the face line
    if face == '+y':
        t, d, lo, hi = -x, y1 - y, -x1 - 1, -x0 + 1
    elif face == '-y':
        t, d, lo, hi = x, y - y0, x0 - 1, x1 + 1
    elif face == '+x':
        t, d, lo, hi = y, x1 - x, y0 - 1, y1 + 1
    else:
        t, d, lo, hi = -y, x - x0, -y1 - 1, -y0 + 1
    sel = hit & (d > -2.0) & (d < a.depth) & (t > lo) & (t < hi)
    zs = z[sel]
    z0, z1 = (a.z if a.z else (float(zs.min()) - 1, float(zs.max()) + 1))
    px = a.px
    Wo, Ho = int((hi - lo) * px), int((z1 - z0) * px)
    acc = np.zeros((Ho, Wo, 3), np.float64)
    cnt = np.zeros((Ho, Wo), np.float64)
    ti = ((t[sel] - lo) * px).astype(int)
    zi = ((z1 - z[sel]) * px).astype(int)
    ok = (ti >= 0) & (ti < Wo) & (zi >= 0) & (zi < Ho)
    np.add.at(acc, (zi[ok], ti[ok]), img[sel][ok])
    np.add.at(cnt, (zi[ok], ti[ok]), 1)
    out = np.full((Ho, Wo, 3), 255.0)
    m = cnt > 0
    out[m] = acc[m] / cnt[m][:, None]
    # fill the small holes (the picture is coarser than the elevation) from the neighbours
    from scipy import ndimage
    if (~m).any():
        idx = ndimage.distance_transform_edt(~m, return_distances=False, return_indices=True)
        dist = ndimage.distance_transform_edt(~m)
        near = dist <= 3
        out[~m & near] = out[idx[0][~m & near], idx[1][~m & near]]
    im = Image.fromarray(out.clip(0, 255).astype(np.uint8))
    g = ImageDraw.Draw(im)
    f = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 11)
    sign = {'+y': -1, '-y': 1, '+x': 1, '-x': -1}[face]
    axis = 'x' if face in ('+y', '-y') else 'y'
    for k in range(math.ceil(lo), int(hi) + 1):
        X = (k - lo) * px
        major = k % 5 == 0
        g.line([(X, 0), (X, 14 if major else 6)], fill=(255, 0, 0))
        g.line([(X, Ho - (14 if major else 6)), (X, Ho)], fill=(255, 0, 0))
        if major:
            g.text((X + 2, 14), f'{axis}{sign * k:+d}', fill=(255, 0, 0), font=f)
    for k in range(math.ceil(z0), int(z1) + 1):
        Y = (z1 - k) * px
        major = k % 5 == 0
        g.line([(0, Y), (14 if major else 6, Y)], fill=(0, 0, 255))
        g.line([(Wo - (14 if major else 6), Y), (Wo, Y)], fill=(0, 0, 255))
        if major:
            g.text((16, Y - 6), str(k), fill=(0, 0, 255), font=f)
    im.save(a.out)
    print(a.out, im.size, f'{axis} {sign * lo:+.1f}..{sign * hi:+.1f} (left to right), z {z0:.1f}..{z1:.1f}', 'pixels used', int(ok.sum()))


if __name__ == '__main__':
    main()
