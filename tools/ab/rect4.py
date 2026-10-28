"""One facade of a render as a flat elevation in metres, from points picked on the render.

A facade is a plane, so its picture is a projective transform of the elevation: four or more
points with known places on the face (t along it, z up) fix it. The output has a metre grid, so
band heights, the ends of bands, window widths and the like can be read off in metres.

    tools/ab/py tools/ab/rect4.py IMAGE OUT.png --pts "u,v,t,z; u,v,t,z; ..." --t T0 T1 --z Z0 Z1 [--px 20]
"""
import argparse
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def homography(src, dst):
    """3x3 H with dst ~ H @ src (least squares over all points)."""
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vt = np.linalg.svd(np.array(A, float))
    H = vt[-1].reshape(3, 3)
    return H / H[2, 2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('image')
    ap.add_argument('out')
    ap.add_argument('--pts', required=True)
    ap.add_argument('--t', nargs=2, type=float, required=True)
    ap.add_argument('--z', nargs=2, type=float, required=True)
    ap.add_argument('--px', type=float, default=20)
    ap.add_argument('--grid', type=float, default=1.0)
    a = ap.parse_args()
    pts = [[float(v) for v in p.split(',')] for p in a.pts.split(';') if p.strip()]
    uv = [(p[0], p[1]) for p in pts]
    tz = [(p[2], p[3]) for p in pts]
    H = homography(tz, uv)
    err = []
    for (t, z), (u, v) in zip(tz, uv):
        q = H @ [t, z, 1]
        err.append(math.hypot(q[0] / q[2] - u, q[1] / q[2] - v))
    t0, t1 = a.t
    z0, z1 = a.z
    W, Hh = int((t1 - t0) * a.px), int((z1 - z0) * a.px)
    img = np.asarray(Image.open(a.image).convert('RGB')).astype(np.float32)
    ih, iw = img.shape[:2]
    ts = t0 + (np.arange(W) + 0.5) / a.px
    zs = z1 - (np.arange(Hh) + 0.5) / a.px
    T, Z = np.meshgrid(ts, zs)
    q = np.stack([T, Z, np.ones_like(T)], axis=-1) @ H.T
    u, v = q[..., 0] / q[..., 2], q[..., 1] / q[..., 2]
    ok = (u >= 0) & (u < iw - 1) & (v >= 0) & (v < ih - 1)
    u, v = np.clip(u, 0, iw - 1.001), np.clip(v, 0, ih - 1.001)
    ui, vi = u.astype(int), v.astype(int)
    fu, fv = (u - ui)[..., None], (v - vi)[..., None]
    c = img[vi, ui] * (1 - fu) * (1 - fv) + img[vi, ui + 1] * fu * (1 - fv) + img[vi + 1, ui] * (1 - fu) * fv + img[vi + 1, ui + 1] * fu * fv
    c[~ok] = 255
    out = Image.fromarray(c.astype(np.uint8))
    g = ImageDraw.Draw(out)
    f = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 11)
    step = a.grid
    k = math.ceil(t0 / step)
    while k * step <= t1:
        m = k * step
        X = (m - t0) * a.px
        major = abs(m / 5 - round(m / 5)) < 1e-6
        g.line([(X, 0), (X, 16 if major else 7)], fill=(255, 0, 0))
        g.line([(X, Hh - (16 if major else 7)), (X, Hh)], fill=(255, 0, 0))
        if major:
            g.text((X + 2, 16), f'{m:g}', fill=(255, 0, 0), font=f)
        k += 1
    k = math.ceil(z0 / step)
    while k * step <= z1:
        m = k * step
        Y = (z1 - m) * a.px
        major = abs(m / 5 - round(m / 5)) < 1e-6
        g.line([(0, Y), (16 if major else 7, Y)], fill=(0, 0, 255))
        g.line([(W - (16 if major else 7), Y), (W, Y)], fill=(0, 0, 255))
        if major:
            g.text((18, Y - 6), f'{m:g}', fill=(0, 0, 255), font=f)
        k += 1
    out.save(a.out)
    print(a.out, out.size, 'fit error px:', ' '.join(f'{e:.1f}' for e in err))


if __name__ == '__main__':
    main()
