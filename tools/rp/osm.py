"""The neighbourhood from OpenStreetMap (© OpenStreetMap contributors, ODbL) -> blender/rp/osm.json.

Buildings with their storeys (building:levels; none given: 4), the roads by class, in site metres
(blender/rp/config.py: x east, y north, 0 at the middle of block Б). The buildings on the plot (the
old houses at кӯчаи Ҳусейнзода 4-8 that make way for the complex) and the two streets the complex
stands on (modelled in blender/rp/site.py) are left out.

    tools/ab/py tools/rp/osm.py            # needs build/rp/osm_q2.json (Overpass: buildings, roads)
"""
import json
import math
import os
import sys

from shapely.geometry import LineString, Polygon, box
from shapely import affinity

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'blender'))
from rp import config as C  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
LAT0, LON0 = 38.56620, 68.78680
WIDTH = {'primary': 16, 'secondary': 14, 'tertiary': 12, 'residential': 8, 'unclassified': 7, 'living_street': 6,
         'service': 5, 'pedestrian': 4, 'footway': 0, 'path': 0, 'steps': 0, 'track': 4}


def en(la, lo):
    return ((lo - LON0) * 111320 * math.cos(math.radians(LAT0)), (la - LAT0) * 110574)


def site(la, lo):
    return C.osm_to_site(*en(la, lo))


def main():
    fr = C.frame_info()
    plot = Polygon([C.sheet_to_site(*p) for p in [(-82, -66), (24, -66), (24, 22), (-82, 22)]])
    D = json.load(open(os.path.join(ROOT, 'build', 'rp', 'osm_q2.json')))
    out = dict(buildings=[], roads=[], places=[])
    for e in D['elements']:
        t = e.get('tags', {})
        g = e.get('geometry')
        if e['type'] == 'node':
            if t.get('amenity') in ('hospital', 'school', 'kindergarten', 'university') and t.get('name'):
                out['places'].append(dict(kind=t['amenity'], name=t.get('name:ru') or t['name'], tj=t['name'], at=[round(v, 1) for v in site(e['lat'], e['lon'])]))
            continue
        if not g:
            continue
        pts = [site(p['lat'], p['lon']) for p in g]
        if 'building' in t and len(pts) >= 4:
            poly = Polygon(pts).buffer(0)
            if poly.is_empty or poly.area < 20 or poly.intersects(plot):
                continue
            lv = t.get('building:levels')
            try:
                lv = float(lv)
            except (TypeError, ValueError):
                lv = None
            poly = max(getattr(poly, 'geoms', [poly]), key=lambda q: q.area)
            out['buildings'].append(dict(ring=[[round(x, 2), round(y, 2)] for x, y in list(poly.exterior.coords)[:-1]],
                                         levels=lv, kind=t.get('building'), name=t.get('name:ru') or t.get('name'),
                                         amenity=t.get('amenity')))
        elif 'highway' in t:
            hw = t['highway']
            name = t.get('name', '')
            if 'Нарзиқул' in name or 'Ҳусейнзода' in name:
                continue
            w = WIDTH.get(hw, 0)
            line = LineString(pts)
            if not w or line.length < 5:
                continue
            if line.intersects(plot.buffer(2)):
                continue
            out['roads'].append(dict(line=[[round(x, 2), round(y, 2)] for x, y in pts], w=w, kind=hw, name=name))
    json.dump(out, open(os.path.join(ROOT, 'blender', 'rp', 'osm.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    print(len(out['buildings']), 'buildings', len(out['roads']), 'roads', [(p['kind'], p['name'], p['at']) for p in out['places']])


if __name__ == '__main__':
    main()
