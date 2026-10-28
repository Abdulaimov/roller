"""Doorways per room, from the plan data the viewer uses (blender/ab/plans.json).

A doorway is a stretch of a room's outline with no wall, column, window or glazing on it and
another room (or the stair hall) across it, 0.5-1.3 m long; longer stretches are open-plan
connections. Prints every room with more than one way to the same neighbour, more doorways than
the drawing has door symbols, or no way in at all.

    tools/ab/py tools/ab/check_doors.py [KEY ...]
"""
import json
import os
import sys
from collections import defaultdict

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.dirname(__file__))
from extract_plan import facing  # noqa: E402


def openings(plan):
    solid = unary_union([Polygon(w).buffer(0) for w in plan['walls'] + plan['struct'] + plan['windows'] + plan['glazing']])
    solid = solid.buffer(0.085)  # the viewer looks 3 and 8 cm behind a room's edge for a wall
    rooms = []
    for ai, a in enumerate(plan['apartments']):
        for ri, r in enumerate(a['rooms'] + a['balconies']):
            rooms.append(dict(id=(ai, ri), apt=ai, kind=r['kind'], area=r['area'], poly=Polygon(r['poly']).buffer(0)))
    for ci, c in enumerate(plan['common']):
        rooms.append(dict(id=('c', ci), apt=None, kind='common', area=Polygon(c).area, poly=Polygon(c).buffer(0)))
    out = defaultdict(list)
    for r in rooms:
        # what lies across each free piece of the outline, looking out from the room
        for q, f in facing(r, r['poly'].exterior.difference(solid), rooms):
            if q is None or f.length < 0.4:
                continue
            out[r['id']].append(dict(to=q['id'], kind_to=q['kind'], apt_to=q['apt'], length=round(f.length, 2),
                                     mid=f.interpolate(0.5, normalized=True)))
    return rooms, out


def main():
    plans = json.load(open(os.path.join(ROOT, 'blender', 'ab', 'plans.json')))
    keys = sys.argv[1:] or list(plans)
    total = 0
    for key in keys:
        rooms, out = openings(plans[key])
        byid = {r['id']: r for r in rooms}
        bad = []
        for r in rooms:
            if r['kind'] == 'common':
                continue
            ops = out.get(r['id'], [])
            # to another flat: never
            foreign = [o for o in ops if o['apt_to'] not in (None, r['apt'])]
            per = defaultdict(int)
            for o in ops:
                per[o['to']] += 1
            dup = {k: v for k, v in per.items() if v > 1 and not (byid[k]['kind'] in ('loggia', 'terrace') or r['kind'] in ('loggia', 'terrace'))}
            # a room and a loggia or terrace: one door between them (longer open stretches aside)
            air = defaultdict(int)
            for o in ops:
                if o['length'] <= 1.3 and (o['kind_to'] in ('loggia', 'terrace')) != (r['kind'] in ('loggia', 'terrace')):
                    air[o['to']] += 1
            dup.update({k: v for k, v in air.items() if v > 1})
            doors = [o for o in ops if o['length'] <= 1.3]
            small = r['kind'] == 'loggia' and r['area'] <= 2.6  # behind the screens, reached by no door
            if foreign or dup or (not ops and not small) or (r['kind'] in ('bath', 'wc', 'storage', 'bedroom') and len(doors) > 1 and r['kind'] != 'bedroom') :
                bad.append((r, ops, foreign, dup))
        print(f'{key}: {len(rooms)} rooms, {sum(len(v) for v in out.values())} openings, {len(bad)} suspicious')
        for r, ops, foreign, dup in bad:
            desc = ', '.join(f"{byid[o['to']]['kind']}{'*' if o['apt_to'] not in (None, r['apt']) else ''} {o['length']}m" for o in ops)
            why = 'to another flat' if foreign else 'twice to the same room' if dup else 'no way in' if not ops else 'several doors'
            print(f"   flat {r['apt']:>2} {r['kind']:8} {r['area']:6.2f} m2: {why}: {desc}")
        total += len(bad)
    print('suspicious rooms:', total)


if __name__ == '__main__':
    main()
