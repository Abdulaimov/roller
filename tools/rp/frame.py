"""Where the three blocks stand relative to each other, and the outline of the shop floors.

All plan sheets draw the blocks in their true places at one scale. The common frame is block Б's
(x right along the sheet, y up the sheet, metres, 0 at the middle of Б's axes). For each block: the
middle of its axes in that frame (from the typical-floor sheet). The podium: the outline of
everything drawn on the sheets of floors 1 and 2 (shops, lobbies, ramps), in the same frame.

    tools/ab/py tools/rp/frame.py        # -> blender/rp/frame.json, build/rp/podium_*.png
"""
import json
import os
import sys

import cv2
import numpy as np
from scipy import ndimage as ndi
from shapely.geometry import Polygon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract as E  # noqa: E402
import sheet as SH  # noqa: E402

OUT = os.path.join(SH.ROOT, 'blender', 'rp', 'frame.json')


def centres(pg):
    frs = {k: SH.fit(pg, k)[0] for k in ('A', 'B', 'V')}
    b = frs['B']
    out = {}
    for k, fr in frs.items():
        x, y = fr.to_sheet(0, 0)          # the block's own plan origin on the sheet
        out[k] = [round(float(v), 3) for v in b.to_plan(x, y)]
    return out, b


def outline(pg, bfr, key):
    # everything round all three blocks, in Б's frame
    R = E.Raster(pg, bfr, (62.0, 6.5, 35.0, 4.5))
    white = R.img.min(axis=2) > 238
    ink = ~white & ~R.cls('green', 40) & ~R.cls('grey', 30)
    ink = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_OPEN, E.sq(5))
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, E.sq(25))
    ink = ndi.binary_fill_holes(ink)
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), 8)
    m = np.isin(lab, [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > 150 * R.ppm ** 2])
    os.makedirs(os.path.join(SH.ROOT, 'build', 'rp'), exist_ok=True)
    cv2.imwrite(os.path.join(SH.ROOT, 'build', 'rp', f'podium_{key}.png'), cv2.resize(m.astype(np.uint8) * 255, (m.shape[1] // 6, m.shape[0] // 6)))
    out = []
    n, lab = cv2.connectedComponents(m.astype(np.uint8), connectivity=8)
    for i in range(1, n):
        out.append(E.trace(lab == i, R, 0.08))
    return out


def main():
    d = SH.doc()
    c, bfr = centres(d[SH.PAGES['typ']])
    info = dict(centres=c)
    for key, sheet in (('floor1', 's1'), ('floor2', 's2')):
        pg = d[SH.PAGES[sheet]]
        _, b2 = centres(pg)
        info[key] = outline(pg, b2, key)
        print(key, [round(Polygon(p).area, 1) for p in info[key]], 'm2')
    print('centres', c)
    json.dump(info, open(OUT, 'w'), separators=(',', ':'))


if __name__ == '__main__':
    main()
