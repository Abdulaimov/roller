"""Regnum Plaza (Baytullo Sokhtmon): three blocks on a common two-storey podium, Dushanbe.

The sales book draws all three blocks on every plan sheet in their true places (tools/rp/frame.py
gives each block's centre in block Б's frame, x right / y up the sheet, metres). On the ground the
sheets' top edge is кӯчаи И. Нарзиқулова and their right edge кӯчаи Ш. Ҳусейнзода (the «Схема
блокировки» on every sheet); on the city map these streets run at bearings 139.5° and 49.5°, so the
sheet is turned 49.5° clockwise: sheet +x points south-east, +y north-east.

Site metres here: x east, y north, 0 at the middle of block Б's axes. OSM (the neighbourhood) is in
metres east / north of 38.5662 N, 68.7868 E; Б's middle is at OSM (-85.9, 59.8) (its outer corner a
pavement's width from the crossing of the two streets).

Heights (no sections in the book): floor 1 at 0 (the shops; the sheets mark +0.000 and +3.000 on its
split levels and +6.000 / +4.500 on floor 2), two shop floors of 4.5 m, so floor 3 at 9.0 m, then
3.3 m per apartment floor.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROT = -49.5            # degrees: sheet x-axis from east towards north
OSM_ORIGIN = (-85.9, 59.8)

GROUND = 4.5
SECOND = 4.5
STOREY = 3.3
SLAB = 0.25
FIRST_FLAT_FLOOR = 3


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
