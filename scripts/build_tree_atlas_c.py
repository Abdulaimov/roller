"""Atlas c: tree kinds added after atlases a and b were packed (21.10.2026: 'full', the full-crowned
broadleaf of the courtyards). Packs only these, in 512 px views, into public/trees/c_*.webp and adds
them to public/trees/trees.json (atlases a and b and their entries stay as they are; their source
renders are not needed).

    blender -b --factory-startup -P blender/trees/render_trees.py -- --only full
    python3 scripts/build_tree_atlas_c.py
"""
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_tree_atlas import OUT, SRC, VIEWS, dilate, shape_normals  # noqa: E402

W, H, CELL = 2048, 1024, 512
LAYOUT = {'full': 0}


def main():
    meta = json.load(open(os.path.join(SRC, 'trees.json')))
    color = np.zeros((H, W, 4), np.float32)
    normal = np.tile(np.array([0.5, 0.5, 1.0], np.float32), (H, W, 1))
    out = json.load(open(os.path.join(OUT, 'trees.json')))
    per_row = W // CELL
    for name, row0 in LAYOUT.items():
        cells = {}
        for i, v in enumerate(VIEWS):
            col, row = i % per_row, row0 + i // per_row
            x0, y0 = col * CELL, row * CELL
            c = np.asarray(Image.open(os.path.join(SRC, f'{name}_{v}_color.png')).convert('RGBA').resize((CELL, CELL), Image.LANCZOS), np.float32) / 255
            n = np.asarray(Image.open(os.path.join(SRC, f'{name}_{v}_normal.png')).convert('RGBA').resize((CELL, CELL), Image.LANCZOS), np.float32) / 255
            a = c[..., 3]
            color[y0:y0 + CELL, x0:x0 + CELL, :3] = dilate(c[..., :3], a)
            color[y0:y0 + CELL, x0:x0 + CELL, 3] = a
            normal[y0:y0 + CELL, x0:x0 + CELL] = dilate(shape_normals(a, n[..., :3], top=(v == 'top')), a)
            cells[v] = [round(x0 / W, 6), round(1 - (y0 + CELL) / H, 6), round(CELL / W, 6), round(CELL / H, 6)]
        m = meta[name]
        out[name] = dict(atlas='c_', height=m['height'], radius=m['radius'], side=m['side_size'], top=m['top_size'],
                         cells=cells, source=m['source'], licence=m['licence'])
    ci = Image.fromarray((np.clip(color, 0, 1) * 255 + 0.5).astype(np.uint8))
    ni = Image.fromarray((np.clip(normal, 0, 1) * 255 + 0.5).astype(np.uint8))
    for tag, k in (('2k', 1), ('1k', 2)):
        ci.resize((W // k, H // k), Image.LANCZOS).save(os.path.join(OUT, f'c_color_{tag}.webp'), 'WEBP', quality=88, method=6)
        ni.resize((W // k, H // k), Image.LANCZOS).save(os.path.join(OUT, f'c_normal_{tag}.webp'), 'WEBP', quality=90, method=6)
    json.dump(out, open(os.path.join(OUT, 'trees.json'), 'w'), indent=1)
    print('atlas c', {k: (out[k]['height'], out[k]['radius']) for k in LAYOUT})


if __name__ == '__main__':
    main()
