"""Check the plans: the extracted rooms, walls and windows drawn over the PDF sheet itself.

    tools/ab/py tools/ab/overlay_plans.py   # -> build/plans/KEY_overlay.png
"""
import json
import os
import sys

import pymupdf
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
import extract_plan as E  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
plans = json.load(open(os.path.join(ROOT, 'blender', 'ab', 'plans.json')))
KC = {'living': (255, 170, 40), 'bedroom': (60, 120, 255), 'kitchen': (255, 60, 60), 'hall': (140, 140, 90), 'bath': (0, 190, 200),
      'wc': (0, 150, 170), 'storage': (170, 90, 220), 'loggia': (60, 200, 60), 'terrace': (30, 150, 30)}
for key, info in E.SHEET_INFO.items():
    sh = E.Sheet(key)
    dpi = 110
    k = dpi / 72
    pix = sh.pg.get_pixmap(dpi=dpi)
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).convert('RGBA')
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    g = ImageDraw.Draw(ov)

    def T(p):  # plan metres -> sheet pixels (inverse of Sheet.P)
        x, y = p
        if info['swap']:
            dx, dy = y, x
        else:
            dx, dy = x, -y
        return ((sh.cx + dx * sh.s) * k, (sh.cy + dy * sh.s) * k)
    pl = plans[key]
    for w in pl['walls'] + pl['struct']:
        g.polygon([T(p) for p in w], fill=(0, 0, 0, 90))
    for w in pl['windows'] + pl['glazing']:
        g.polygon([T(p) for p in w], fill=(0, 160, 255, 200))
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 11)
    except OSError:
        font = None
    for a in pl['apartments']:
        g.polygon([T(p) for p in a['outline']], outline=(255, 0, 150, 255), width=2)
        for r in a['rooms'] + a['balconies']:
            c = KC.get(r['kind'], (128, 128, 128))
            g.polygon([T(p) for p in r['poly']], fill=c + (70,), outline=c + (255,))
            xs = [T(p)[0] for p in r['poly']]
            ys = [T(p)[1] for p in r['poly']]
            g.text(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2), r['kind'][:4], fill=(0, 0, 0, 255), font=font, anchor='mm')
        xs = [T(p)[0] for p in a['outline']]
        ys = [T(p)[1] for p in a['outline']]
        g.text(((min(xs) + max(xs)) / 2, min(ys) + 14), f"{a['rooms_count']}к {a['area']}", fill=(200, 0, 120, 255), font=font, anchor='mm')
    out = Image.alpha_composite(im, ov).convert('RGB')
    out.save(os.path.join(ROOT, 'build', 'plans', f'{key}_overlay.png'))
    print(key, out.size)
