"""What the plans read off the sales book come to, room by room (blender/rp/plans.json):
  - outlines whose area is far from the area the sheet writes in the room (more than 12% and 1 m²);
  - bedrooms, living rooms and kitchens without their main piece read from the drawing (bed or sofa,
    sofa or armchairs, kitchen run) - those the viewer furnishes itself;
  - rooms the sheet signs as one kind but draws as another (taken as drawn).

    tools/ab/py tools/rp/rooms_report.py [PLAN ...]
"""
import json
import os
import sys

from shapely.geometry import Point, Polygon

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# (a studio's one room has the bed for its main piece: А's flats 2 and 181)
MAIN = {'bedroom': ('bed', 'sofa'), 'living': ('sofa', 'armchair', 'bed'), 'kitchen': ('kitchen', 'sofa')}


def centre(it):
    if 'c' in it:
        return it['c']
    b = it['boxes']
    return [sum(x[0] for x in b) / len(b), sum(x[1] for x in b) / len(b)]


def main():
    P = json.load(open(os.path.join(ROOT, 'blender', 'rp', 'plans.json')))
    keys = sys.argv[1:] or list(P)
    off = rooms = empty = mains = 0
    for key in keys:
        for i, a in enumerate(P[key]['apartments']):
            for r in a['rooms'] + a['balconies']:
                rooms += 1
                area = Polygon(r['poly']).buffer(0).area
                if abs(area - r['area']) > max(1.0, 0.12 * r['area']):
                    off += 1
                    print(f'outline  {key} flat {i}: {r["label"] or r["kind"]} {r["area"]} m², outline {area:.2f}')
                if 'sheet' in r:
                    print(f'as drawn {key} flat {i}: «{r["label"]}» {r["area"]} m² is drawn as a {r["kind"]}')
                if r['kind'] not in MAIN:
                    continue
                mains += 1
                rp = Polygon(r['poly']).buffer(0.1)
                got = {it['type'] for it in a['furniture'] if rp.contains(Point(*centre(it)))}
                if not got & set(MAIN[r['kind']]):
                    empty += 1
                    print(f'no main  {key} flat {i}: {r["kind"]} {r["area"]} m² ({", ".join(sorted(got)) or "nothing read"})')
    print(f'{off} of {rooms} outlines off; {empty} of {mains} bedrooms, living rooms and kitchens without their main piece from the drawing')


if __name__ == '__main__':
    main()
