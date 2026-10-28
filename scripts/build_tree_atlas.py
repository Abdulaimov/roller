"""Pack the tree views rendered by blender/trees/render_trees.py into the atlas the site loads.

    python3 scripts/build_tree_atlas.py          # needs: pip install pillow numpy

public/trees/{a,b}_color_{2k,1k}.webp   colour + alpha (cut-out), full size for computers, half for phones
public/trees/{a,b}_normal_{2k,1k}.webp  normals in each view's frame: the crown's rounded shape from its
                                  silhouette, with some leaf detail from the render on top
public/trees/trees.json           per variant: size in metres, where each view sits in the atlas

Layout: atlas a (2048 x 2048) holds the two broadleaf street trees, the most common, in 512 px
views; atlas b (2048 x 1024) the conifers, narrow and small trees in 256 px views. Colours are pushed out past the cut-out edge
so mip levels don't grow dark fringes round the leaves.
"""
import json
import os

import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = os.path.join(ROOT, 'build', 'trees')
OUT = os.path.join(ROOT, 'public', 'trees')
VIEWS = ['side0', 'side1', 'side2', 'side3', 'side4', 'side5', 'top']
# two atlases: 'a' the broadleaf street trees (most of the trees, the largest on screen) in 512 px
# views, 4 to a row; 'b' the conifers, narrow trees and small trees in 256 px views, 8 to a row
ATLASES = {'a': (2048, 2048, 512), 'b': (2048, 1024, 256)}
LAYOUT = {'broad': ('a', 0), 'broad_b': ('a', 2), 'fir_a': ('b', 0), 'fir_b': ('b', 1), 'poplar': ('b', 2), 'shrub': ('b', 3)}


def dilate(rgb, alpha, steps=24):
    """Fill transparent pixels with the colour of the nearest opaque ones (repeated 3x3 averaging)."""
    rgb = rgb.copy()
    known = alpha > 0.02
    for _ in range(steps):
        if known.all():
            break
        acc = np.zeros_like(rgb)
        cnt = np.zeros(known.shape, np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                k = np.roll(np.roll(known, dy, 0), dx, 1)
                acc += np.roll(np.roll(rgb * known[..., None], dy, 0), dx, 1)
                cnt += k
        grow = (~known) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        known = known | grow
    rgb[~known] = rgb[known].mean(axis=0) if known.any() else 0.5
    return rgb


def shape_normals(alpha, detail, top=False):
    """Normals for a billboard: the rounded shape of the crown, read from the silhouette, plus some
    of the leaf-level detail from the render. A crown lit through these is light on the sun side and
    dark on the other, as a real crown is, without the noise of single leaves turned away."""
    H, W = alpha.shape
    m = alpha > 0.3
    n = np.zeros((H, W, 3), np.float32)
    n[..., 2] = 1
    if not m.any():
        return n
    ys, xs = np.nonzero(m)
    if top:
        cx, cy = xs.mean(), ys.mean()
        r = max(np.percentile(np.hypot(xs - cx, ys - cy), 95), 1)
        X, Y = np.meshgrid(np.arange(W), np.arange(H))
        nx, ny = (X - cx) / r * 0.75, -(Y - cy) / r * 0.75
    else:
        X = np.arange(W)[None, :].repeat(H, 0).astype(np.float32)
        nx = np.zeros((H, W), np.float32)
        # each row: across its own width, like a column of foliage (or the trunk)
        for y in range(H):
            row = np.nonzero(m[y])[0]
            if len(row) < 2:
                continue
            c, hw = (row[0] + row[-1]) / 2, max((row[-1] - row[0]) / 2, 1)
            nx[y] = (X[y] - c) / hw * 0.8
        # up and down over the crown: rows of the crown are those wider than a quarter of the widest
        widths = np.array([np.ptp(np.nonzero(m[y])[0]) if m[y].sum() > 1 else 0 for y in range(H)])
        crown = np.nonzero(widths > 0.25 * widths.max())[0]
        y0, y1 = (crown.min(), crown.max()) if len(crown) else (0, H - 1)
        cy, ry = (y0 + y1) / 2, max((y1 - y0) / 2, 1)
        Y = np.arange(H)[:, None].repeat(W, 1).astype(np.float32)
        ny = np.where((Y >= y0) & (Y <= y1), -(Y - cy) / ry * 0.55, 0)
        ny[Y > y1] = 0
    nx, ny = np.clip(nx, -0.95, 0.95), np.clip(ny, -0.95, 0.95)
    nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0.05, 1))
    d = detail * 2 - 1
    out = np.stack([nx + 0.35 * d[..., 0], ny + 0.35 * d[..., 1], nz + 0.35 * np.abs(d[..., 2])], axis=-1)
    out /= np.linalg.norm(out, axis=-1, keepdims=True)
    return out * 0.5 + 0.5


def main():
    meta = json.load(open(os.path.join(SRC, 'trees.json')))
    canvas = {k: (np.zeros((h, w, 4), np.float32), np.tile(np.array([0.5, 0.5, 1.0], np.float32), (h, w, 1))) for k, (w, h, _) in ATLASES.items()}
    out = {}
    for name, (atlas, row0) in LAYOUT.items():
        if name not in meta:
            continue
        W, H, cell = ATLASES[atlas]
        color, normal = canvas[atlas]
        per_row = W // cell
        cells = {}
        for i, v in enumerate(VIEWS):
            col, row = i % per_row, row0 + i // per_row
            x0, y0 = col * cell, row * cell
            c = np.asarray(Image.open(os.path.join(SRC, f'{name}_{v}_color.png')).convert('RGBA').resize((cell, cell), Image.LANCZOS), np.float32) / 255
            n = np.asarray(Image.open(os.path.join(SRC, f'{name}_{v}_normal.png')).convert('RGBA').resize((cell, cell), Image.LANCZOS), np.float32) / 255
            a = c[..., 3]
            color[y0:y0 + cell, x0:x0 + cell, :3] = dilate(c[..., :3], a)
            color[y0:y0 + cell, x0:x0 + cell, 3] = a
            normal[y0:y0 + cell, x0:x0 + cell] = dilate(shape_normals(a, n[..., :3], top=(v == 'top')), a)
            # uv rect (three.js: v = 0 at the bottom of the image)
            cells[v] = [round(x0 / W, 6), round(1 - (y0 + cell) / H, 6), round(cell / W, 6), round(cell / H, 6)]
        m = meta[name]
        out[name] = dict(atlas=f'{atlas}_', height=m['height'], radius=m['radius'], side=m['side_size'], top=m['top_size'],
                         cells=cells, source=m['source'], licence=m['licence'])
    os.makedirs(OUT, exist_ok=True)
    for atlas, (color, normal) in canvas.items():
        W, H, _ = ATLASES[atlas]
        ci = Image.fromarray((np.clip(color, 0, 1) * 255 + 0.5).astype(np.uint8))
        ni = Image.fromarray((np.clip(normal, 0, 1) * 255 + 0.5).astype(np.uint8))
        for tag, k in (('2k', 1), ('1k', 2)):
            ci.resize((W // k, H // k), Image.LANCZOS).save(os.path.join(OUT, f'{atlas}_color_{tag}.webp'), 'WEBP', quality=88, method=6)
            ni.resize((W // k, H // k), Image.LANCZOS).save(os.path.join(OUT, f'{atlas}_normal_{tag}.webp'), 'WEBP', quality=90, method=6)
    json.dump(out, open(os.path.join(OUT, 'trees.json'), 'w'), indent=1)
    print('atlas', {k: (v['atlas'], v['height'], v['radius']) for k, v in out.items()})


if __name__ == '__main__':
    main()
