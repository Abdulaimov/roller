"""Regnum Plaza (Baytullo Sokhtmon): three blocks on a common two-storey podium, Dushanbe.

The sales book draws all three blocks on every plan sheet in their true places (tools/rp/frame.py
gives each block's centre in block Б's frame, x right / y up the sheet, metres). On the ground the
sheets' top edge is кӯчаи И. Нарзиқулова and their right edge кӯчаи Ш. Ҳусейнзода (the «Схема
блокировки» on every sheet); on the city map these streets run at bearings 139.5° and 49.5°, so the
sheet is turned 49.5° clockwise: sheet +x points south-east, +y north-east.

Site metres here: x east, y north, 0 at the middle of block Б's axes. OSM (the neighbourhood) is in
metres east / north of 38.5662 N, 68.7868 E; Б's middle is at OSM (-85.9, 59.8) (its outer corner a
pavement's width from the crossing of the two streets).

Heights (no sections in the book): floor 1 at 0.000 and floor 2 at 6.000, as the sheets' titles give
them («Тарҳи ошёнаи 2-юм дар ниш. 6,000»; the stairs of floor 1 land at +1.500, +3.000, +4.500, the
shops' mezzanine at +3.000). Floor 3 is not marked: the renders give the podium about 3.06 apartment
storeys high (render 3: 98 px against 32 px a storey; render 6: floor 2's glazing two thirds of
floor 1's), so with 3.3 m storeys floor 2 is 4.1 m and floor 3 at 10.1 m (it was 4.5 + 4.5 = 9.0
before 29.10.2026, floor 2 at 4.5 against the sheet's 6.0). The apartment storey (3.3 m) is assumed:
the book has no section.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROT = -49.5            # degrees: sheet x-axis from east towards north
OSM_ORIGIN = (-85.9, 59.8)

GROUND = 6.0
SECOND = 4.1
STOREY = 3.3
SLAB = 0.25
FIRST_FLAT_FLOOR = 3
# the drive down into the basement (sheets 10 and 17: «Пандус», the scheme's two lines from кӯчаи
# Нарзиқулова into В's west end): its door in the podium, sheet x from / to
RAMP_X = (-67.7, -63.4)
# the doors from the courtyard (the scheme's four arrows): В's two on its yard face, Б's in the inner
# corner, А's on its yard face - sheet point on the face and the way out (sheet axes)
DOORS = [((-50.2, -11.6), (0, -1)), ((-38.1, -11.6), (0, -1)), ((-16.2, -13.3), (-1, 0)), ((-11.5, -19.0), (-1, 0))]


def level(n):
    if n <= 1:
        return 0.0
    if n == 2:
        return GROUND
    return GROUND + SECOND + (n - 3) * STOREY


def height(n):
    return GROUND if n == 1 else SECOND if n == 2 else STOREY


def plans_for(key):
    if key == 'A':
        return {**{f: 'A_typ' for f in range(3, 23)}, 23: 'A_23'}
    if key == 'B':
        return {3: 'B_3', **{f: 'B_typ' for f in range(4, 19)}, 19: 'B_19'}
    return {**{f: 'V_typ' for f in range(3, 23)}, 23: 'V_23', 24: 'V_23', 25: 'V_25'}


BLOCKS = {
    'A': dict(label='Блок А', tj='Блоки А', floors=23, style='A'),
    'B': dict(label='Блок Б', tj='Блоки Б', floors=19, style='B'),
    'V': dict(label='Блок В', tj='Блоки В', floors=25, style='V'),
}


def rot(x, y, deg=ROT):
    a = math.radians(deg)
    return (math.cos(a) * x - math.sin(a) * y, math.sin(a) * x + math.cos(a) * y)


def frame_info():
    return json.load(open(os.path.join(HERE, 'frame.json')))


def load_plans():
    return json.load(open(os.path.join(HERE, 'plans.json')))


def setup():
    fr = frame_info()
    for k, b in BLOCKS.items():
        cx, cy = fr['centres'][k]
        b['sheet_centre'] = (cx, cy)
        b['centre'] = rot(cx, cy)
        b['rot'] = ROT
        b['plans'] = plans_for(k)
        b['sales'] = True
    return fr


def sheet_to_site(x, y):
    return rot(x, y)


def osm_to_site(x, y):
    return (x - OSM_ORIGIN[0], y - OSM_ORIGIN[1])
