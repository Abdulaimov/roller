"""The seams between the drawing's walls, columns and glazing closed (23.10.2026: slits in the flats'
walls, floor to ceiling, where a wall stops 0.7-0.9 cm short of a column or of the next wall: the
PDF draws them as separate blocks that do not quite meet). For every plan the walls, columns,
windows and glazing are joined, the union closed (grown by 2 cm, shrunk back): what the closing
adds - gaps under 4 cm wide - is added to the walls. Faces stay where they are; door openings and
anything wider are untouched. Running it again adds nothing.
    tools/ab/py tools/ab/close_seams.py [src/model/plans.json]
"""
import json
import os
import sys

from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'src/model/plans.json')
plans = json.load(open(path))
R = 0.02


def poly(p):
    g = Polygon(p)
    return g if g.is_valid else g.buffer(0)


for key, pl in plans.items():
    parts = [poly(p) for k in ('walls', 'struct', 'windows', 'glazing') for p in pl.get(k, [])]
    union = unary_union([g for g in parts if not g.is_empty])
    closed = union.buffer(R, join_style=2, mitre_limit=4).buffer(-R, join_style=2, mitre_limit=4)
    fill = closed.difference(union)
    pieces = [g for g in getattr(fill, 'geoms', [fill]) if g.geom_type == 'Polygon' and g.area > 2e-5]
    added = []
    for g in pieces:
        # (slivers only, of any shape: nothing of it wider than the closing's 4 cm)
        if not g.buffer(-(R + 0.001)).is_empty:
            continue
        # a little into the pieces on either side: no hairline where it meets them
        g = g.buffer(0.003, join_style=2).intersection(closed.buffer(0.003, join_style=2))
        g = g if g.geom_type == 'Polygon' else max(getattr(g, 'geoms', []), key=lambda q: q.area, default=None)
        if g is None or g.is_empty:
            continue
        added.append([[round(x, 4), round(y, 4)] for x, y in list(g.exterior.coords)[:-1]])
    pl['walls'] = pl['walls'] + added
    print(key, 'seams closed:', len(added), 'area', round(sum(poly(p).area for p in added), 4), 'm2')
json.dump(plans, open(path, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
