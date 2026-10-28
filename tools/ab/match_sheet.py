"""The architect's sheet and the model side by side for one flat, both in plan orientation (plan x
right, plan y up), at the same scale: the model shot from tools/ab/plan_view.mjs is warped with the
three plan points it carries; the sheet is cut out through the extraction's own transform. If the
two do not look alike after this, the model is not the drawing (mirrored, turned, misplaced).

    tools/ab/py tools/ab/match_sheet.py SHOT.png OUT.png [--px 60]
"""
import json
import os
import sys

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
import extract_plan as E  # noqa: E402


def affine(src, dst):
    """2x3 matrix A with dst = A @ [src, 1]"""
    S = np.array([[x, y, 1.0] for x, y in src])
    D = np.array(dst, float)
    A, *_ = np.linalg.lstsq(S, D, rcond=None)
    return A.T


def main():
    shot, out = sys.argv[1:3]
    px = float(sys.argv[sys.argv.index('--px') + 1]) if '--px' in sys.argv else 60.0
    info = json.load(open(shot.replace('.png', '.json')))
    key = info['plan']
    xs = [p[0] for p in info['outline']]
    ys = [p[1] for p in info['outline']]
    x0, y0, x1, y1 = min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1
    W, H = int((x1 - x0) * px), int((y1 - y0) * px)
    # plan -> shot pixels
    A = affine([p['plan'] for p in info['pts']], [p['px'] for p in info['pts']])
    im = np.asarray(Image.open(shot).convert('RGB')).astype(np.float32)

    def sample(img, U, V):
        h, w = img.shape[:2]
        ok = (U >= 0) & (U < w - 1) & (V >= 0) & (V < h - 1)
        U, V = np.clip(U, 0, w - 1.001), np.clip(V, 0, h - 1.001)
        ui, vi = U.astype(int), V.astype(int)
        fu, fv = (U - ui)[..., None], (V - vi)[..., None]
        c = img[vi, ui] * (1 - fu) * (1 - fv) + img[vi, ui + 1] * fu * (1 - fv) + img[vi + 1, ui] * (1 - fu) * fv + img[vi + 1, ui + 1] * fu * fv
        c[~ok] = 255
        return c
    gx, gy = np.meshgrid(x0 + (np.arange(W) + 0.5) / px, y1 - (np.arange(H) + 0.5) / px)
    U = A[0, 0] * gx + A[0, 1] * gy + A[0, 2]
    V = A[1, 0] * gx + A[1, 1] * gy + A[1, 2]
    model = sample(im, U, V)
    # plan -> sheet points (inverse of Sheet.P), the sheet rendered at a high resolution
    sh = E.Sheet(key)
    info_s = E.SHEET_INFO[key]
    dpi = 300
    k = dpi / 72
    pix = sh.pg.get_pixmap(dpi=dpi)
    sheet = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3].astype(np.float32)
    if info_s['swap']:
        dx, dy = gy, gx
    else:
        dx, dy = gx, -gy
    SU = (sh.cx + dx * sh.s) * k
    SV = (sh.cy + dy * sh.s) * k
    drawing = sample(sheet, SU, SV)
    a = Image.fromarray(drawing.astype(np.uint8))
    b = Image.fromarray(model.astype(np.uint8))
    o = Image.new('RGB', (W * 2 + 12, H + 36), 'white')
    o.paste(a, (0, 36))
    o.paste(b, (W + 12, 36))
    g = ImageDraw.Draw(o)
    f = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 18)
    g.text((6, 8), 'Чертёж', fill=(30, 30, 30), font=f)
    g.text((W + 18, 8), 'Модель', fill=(30, 30, 30), font=f)
    o.save(out)
    print(out, o.size)


if __name__ == '__main__':
    main()
