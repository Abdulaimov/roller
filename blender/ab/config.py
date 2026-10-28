"""The Ali Binokor complex: blocks, floors and where they stand (site metres: x east, y north on the
genplan sheet, origin at the middle of the plot; see tools/ab/site_map.py).

Block centres and turns were fitted to the footprints drawn on the genplan (ГП, 1:1000); the floor
plans (plans.json, tools/ab/extract_plan.py) are drawn in each block's own frame and turned by `rot`
(degrees, plan x-axis from east towards north). For the slab blocks the plan's +y side (punched
windows in brick, the stair halls) faces the street as on the renders, and the -y side (the row of
loggias) the courtyard.
There are no sections in the drawings; the heights are read off the client renders (tools/ab/calib.py
fits the renders' cameras to the band, window and cornice rows): two tall shop floors (6.2 m and 5.8 m:
floor 3 is 12.0 m over the street on renders 1 and 2, the tower and the slab blocks alike), then
3.5 m per floor on the slab blocks (render 1: 3.44 m on Б, 3.54 m on В, against the plans' 64.4 m
length) and 3.75 m on the glass tower A (renders 1 and 2 both give 3.74-3.75 m against the plan's
45.7 x 44.2 m curtain wall; 3.3 m misses the band rows by up to 42-49 px).
"""
import json
import os

PLANS_JSON = os.path.join(os.path.dirname(__file__), 'plans.json')

GROUND = 6.2      # floor 1 (shops)
SECOND = 5.8      # floor 2 (shops)
STOREY = 3.5      # apartment floors
SLAB = 0.25       # finished floor above the level datum (the viewer puts interiors on it)


def dims(b=None):
    """(floor 1, floor 2, apartment floor) heights of block b (a BLOCKS entry or its key)"""
    if isinstance(b, str):
        b = BLOCKS[b]
    if not b:
        return GROUND, SECOND, STOREY
    return b.get('ground', GROUND), b.get('second', SECOND), b.get('storey', STOREY)


def level(n, b=None):
    """height of floor n of block b above the ground"""
    g, s, st = dims(b)
    if n <= 1:
        return 0.0
    if n == 2:
        return g
    return g + s + (n - 3) * st


def height(n, b=None):
    g, s, st = dims(b)
    return g if n == 1 else s if n == 2 else st


def podium_top(b=None):
    """roof of the two shop floors = level of floor 3"""
    g, s, _ = dims(b)
    return g + s


# The complex a little more spacious than the genplan draws it (the developer, 21.10.2026: the
# buyers should see that the houses do not stand close together and that the grounds are large):
# the genplan's site is scaled by SPREAD round the middle of the plot; the blocks keep their size and
# stand at their spread centres. site_raw() gives the genplan so spread.
SPREAD = 1.1


def spread(p):
    return (round(p[0] * SPREAD, 3), round(p[1] * SPREAD, 3))


BLOCKS = {
    # key: label, centre, rot, floors, plan per floor, facade style, sold (interiors) or only shown
    # (gp_centre: where the genplan draws it; centre: spread)
    'A': dict(label='Блок А', tj='Блоки А', gp_centre=(-99.0, -19.5), rot=26.0, floors=24, style='glass', sales=True,
              storey=3.75,
              plans={f: ('A_t' if f in (9, 10, 20, 21) else 'A') for f in range(3, 25)}),
    'B': dict(label='Блок Б', tj='Блоки Б', gp_centre=(-33.6, -31.0), rot=205.2, floors=22, style='brick', sales=True,
              plans={f: ('BG_top' if f >= 19 else 'BG') for f in range(3, 23)}),
    'V': dict(label='Блок В', tj='Блоки В', gp_centre=(44.2, -38.5), rot=205.4, floors=20, style='brick', sales=False,
              plans={f: ('BG_top' if f >= 19 else 'BG') for f in range(3, 21)}),
    'G': dict(label='Блок Г', tj='Блоки Г', gp_centre=(45.37, 49.45), rot=117.5, floors=22, style='brick', sales=True,
              plans={f: ('BG_top' if f >= 19 else 'BG') for f in range(3, 23)}),
    'D': dict(label='Блок Д', tj='Блоки Д', gp_centre=(108.45, 38.13), rot=207.5, floors=22, style='brick', sales=False,
              plans={f: ('BG_top' if f >= 19 else 'BG') for f in range(3, 23)}),
}
for _b in BLOCKS.values():
    _b['centre'] = spread(_b['gp_centre'])
FIRST_FLAT_FLOOR = 3

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')


def site_raw():
    """build/site_raw.json (the genplan read off the sheet, tools/ab/site_map.py), spread: every
    point scaled by SPREAD round the middle of the plot, except the footprints drawn for the blocks
    and their two-storey podiums (classes building and podium within 45 m of a block's genplan
    centre), which move with their block and keep their size."""
    raw = json.load(open(os.path.join(ROOT, 'build', 'site_raw.json')))
    S = SPREAD
    sc = lambda pts: [[round(x * S, 3), round(y * S, 3)] for x, y in pts]
    def shifted(pts, d):
        return [[round(x + d[0], 3), round(y + d[1], 3)] for x, y in pts]
    for cls, items in raw['classes'].items():
        for it in items:
            ring = it['ring']
            cx = sum(p[0] for p in ring) / len(ring)
            cy = sum(p[1] for p in ring) / len(ring)
            near = [b['gp_centre'] for b in BLOCKS.values() if (cx - b['gp_centre'][0]) ** 2 + (cy - b['gp_centre'][1]) ** 2 < 45 ** 2]
            if cls in ('building', 'podium') and near:
                d = ((S - 1) * near[0][0], (S - 1) * near[0][1])
                it['ring'] = shifted(ring, d)
                it['holes'] = [shifted(h, d) for h in it['holes']]
            else:
                it['ring'] = sc(ring)
                it['holes'] = [sc(h) for h in it['holes']]
    raw['trees'] = sc(raw['trees'])
    raw['plot'] = sc(raw['plot'])
    raw['kinder'] = [sc(r) for r in raw.get('kinder', [])]
    raw['blue'] = [sc(r) for r in raw.get('blue', [])]
    for w in raw['words']:
        w['p'] = [round(w['p'][0] * S, 3), round(w['p'][1] * S, 3)]
    return raw


def load_plans():
    return json.load(open(PLANS_JSON))
