"""The clouds of the HDRI (Poly Haven, CC0) cut out of its sky, for the viewer's sky (src/world.js):
the photographed cumulus over the drawn deep blue (23.10.2026: the drawn clouds read as smears next
to real ones). The upper half of the panorama (horizon to zenith, v = elevation / 90): RGB the
clouds' light (linear, x1.7 as the old background showed them, stored as sqrt(c / 3)), alpha how
much cloud there is. A pixel is cloud as far as it is whiter than that row's clear sky; round the
sun (its glare) and right at the horizon (haze) there is none. The blue-sky part of a cloud's edge
pixels is taken out, so the edges are not pale blue over the deeper blue.
    tools/ab/py tools/ab/clouds.py blender/assets/hdri/kloofendal_48d_partly_cloudy_puresky_8k.hdr
-> public/env/clouds_{8k,4k,2k}.webp (8k only for the TV film, ?clouds=8k)"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
src = sys.argv[1]
info = json.load(open(os.path.join(ROOT, 'public/env/sky.json')))
im = cv2.imread(src, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_COLOR)[:, :, ::-1].astype(np.float32)
H, W, _ = im.shape
up = im[: H // 2]
h = up.shape[0]
el = 90 - (np.arange(h) + 0.5) / H * 180  # per row, degrees

mx, mn = up.max(2), up.min(2)
w = mn / np.maximum(mx, 1e-6)  # whiteness: 1 grey or white, lower the bluer
# each row's clear sky: its bluer pixels
wc = np.percentile(w, 25, axis=1)[:, None]
clear = np.empty((h, 3), np.float32)
for r in range(h):
    sel = w[r] <= np.percentile(w[r], 30)
    clear[r] = np.median(up[r][sel], axis=0)
a = np.clip((w - (wc + 0.035)) / np.maximum(0.86 - wc, 0.06), 0, 1)
m = a * a * (3 - 2 * a)

# none round the sun (the photo's glare) and at the horizon (haze; the viewer's own haze is there)
u = (np.arange(W) + 0.5) / W
az = (u - 0.5) * 2 * np.pi
er = np.radians(el)[:, None]
d = np.stack([np.cos(er) * np.cos(az)[None, :], np.repeat(np.sin(er), W, 1), np.cos(er) * np.sin(az)[None, :]], -1)
s = np.array(info['sun_dir'], np.float32)
ang = np.degrees(np.arccos(np.clip(d @ (s / np.linalg.norm(s)), -1, 1)))
k = np.clip((ang - 9) / 13, 0, 1)
m *= k * k * (3 - 2 * k)
k = np.clip((el[:, None] - 0.4) / 3.0, 0, 1)
m *= k * k * (3 - 2 * k)

# the cloud's own light: the clear sky taken out of the edge pixels
c = (up - (1 - m)[..., None] * clear[:, None, :]) / np.maximum(m, 0.25)[..., None]
c = np.clip(c, 0, None) * 1.7
rgb = np.sqrt(np.clip(c / 3, 0, 1))
out = np.dstack([rgb, m])
out8 = (out * 255 + 0.5).astype(np.uint8)
print('cloud cover', round(float(m.mean()), 3), 'size', W, h)
for name, width in (('8k', 8192), ('4k', 4096), ('2k', 2048)):
    if width > W:
        continue
    img = out8 if width == W else cv2.resize(out8, (width, width // 4), interpolation=cv2.INTER_AREA)
    path = os.path.join(ROOT, f'public/env/clouds_{name}.webp')
    Image.fromarray(img, 'RGBA').save(path, quality=88, method=6, exact=True)
    print(path, os.path.getsize(path) // 1024, 'KB')
