"""Every door the sheet draws, as the walk-through builds it: is there a doorway, and what stands
across it (collision lines through the doorway's cut, other than its own leaf)?

    node tools/ab/dump_walk.mjs build/rp/compare/walk.json B14-3 [...]
    tools/ab/py tools/rp/door_check.py build/rp/compare/walk.json
"""
import json
import os
import sys

from shapely.geometry import LineString, Point, Polygon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet as SH  # noqa: E402


def main():
    data = json.load(open(sys.argv[1]))
    P = json.load(open(os.path.join(SH.ROOT, 'blender', 'rp', 'plans.json')))
    for aid, d in data.items():
        plan = P[d['plan']]
        rooms = [(r['kind'], r['area'], Polygon(r['poly']).buffer(0)) for r in d['rooms']]
        lost = {i for i in range(len(rooms)) if i not in d['reach']['before']}
        for cut in plan.get('doorways', []):
            g = Polygon(cut).buffer(0)
            near = [i for i, (_, _, q) in enumerate(rooms) if q.distance(g) < 0.06]
            if not near or not (set(near) & lost):
                continue
            inner = g.buffer(-0.05)
            hits = [s for s in d['segments'] if LineString([(s[0], s[1]), (s[2], s[3])]).intersects(inner)]
            made = any(Polygon([dw['a'], dw['b'], [dw['b'][0] + dw['n'][0] * 0.05, dw['b'][1] + dw['n'][1] * 0.05], [dw['a'][0] + dw['n'][0] * 0.05, dw['a'][1] + dw['n'][1] * 0.05]]).buffer(0.1).intersects(g) for dw in d['doorways'])
            c = g.centroid
            print(f"{aid}: door at ({c.x:.2f}, {c.y:.2f}) between {', '.join(f'{rooms[i][0]} {rooms[i][1]}' for i in near)}: "
                  f"{'doorway' if made else 'NO doorway'}, {len(hits)} lines across" + (f" e.g. {[round(v, 2) for v in hits[0]]}" if hits else ''))


if __name__ == '__main__':
    main()
