"""Brand signs over every shop: which brand goes where, and the places in site metres for src/signs.js.
Reads build/shopfronts.json (node tools/ab/shopfronts.mjs) and writes the set 'brands' of
public/signs/signs.json; the pictures are tools/ab/brand_signs.py's.
    tools/ab/py tools/ab/place_signs.py [--list]      (--list: the facade runs and their keys only)

Blocks Б, В, Г, Д: the portals are grouped into runs (one straight stretch of facade, portals 4.5 m
apart); a run is split into shops of 1-3 portals. Each shop gets its sign (lit letters on the dark
frieze over its portals, 10.2-11.0 m) and a lit poster behind the second-floor glass of one portal.
Block A: one logo on each straight stretch of the podium's upper white band (11.1-12.45 m).
Street faces (to the avenue) get the fashion houses and the big sports brands, the ends of the blocks
sports and tech, the yard faces everyday shops, cafes and the children's shop."""
import json
import math
import os
import sys

import shapely
from shapely.geometry import MultiPoint, Polygon
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brand_signs import BRANDS  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
FRIEZE = (10.2, 11.0)          # the dark frieze over the portals (podium.py: glass_top + 0.3 .. TOP - 1.0)
SIGN_H = 0.74                  # the sign's height on it (a brand's own 'h' if set)
POSTER = dict(z=8.05, h=3.1, off=-0.35, half=1.3)  # behind the upper glass (6.3-9.8 m, 2.6 m wide), inside
BAND = dict(z=11.775, h=0.85, off=0.09)            # block A: the band's face (11.16-12.39 m), 6 cm chamfer

# run key -> the shops on it, left to right seen from the street: (brand, portals)
RUNS = {
    # Б: the street faces (render 1), its west end, the yard, its east end
    'B155#0': [('gucci', 3)],
    'B185#0': [('louisvuitton', 2)],
    'B185#1': [('rolex', 1)],
    'B155#1': [('prada', 3)],
    'B245#0': [('hugo', 3)],
    'B065#0': [('reebok', 2)],
    'B065#1': [('newbalance', 3)],
    'B335#0': [('lego', 3)],
    'B335#1': [('swarovski', 3)],
    'B335#2': [('pandora', 3)],
    # В
    'V155#0': [('dior', 2)],
    'V185#0': [('boss', 2), ('chanel', 2)],
    'V155#1': [('lacoste', 2), ('versace', 2)],
    'V245#0': [('levis', 3)],
    'V065#0': [('huawei', 2)],
    'V065#1': [('xiaomi', 3)],
    'V335#0': [('sony', 3)],
    'V335#1': [('guess', 3)],
    'V335#2': [('michaelkors', 3)],
    # Г: the street face is the south-west one (render 2)
    'G243#0': [('nike', 3), ('jordan', 2)],
    'G243#1': [('adidas', 3), ('puma', 2)],
    'G152#0': [('skechers', 3)],
    'G333#0': [('converse', 3)],
    'G063#0': [('fila', 3)],
    'G063#1': [('mcdonalds', 3)],
    'G063#2': [('kfc', 3)],
    # Д: the street face is the south-east one
    'D153#0': [('burberry', 3), ('armani', 2)],
    'D153#1': [('calvinklein', 3), ('tommy', 2)],
    'D243#0': [('thenorthface', 3)],
    'D062#0': [('underarmour', 3)],
    'D333#0': [('decathlon', 3)],
    'D333#1': [('columbia', 3)],
    'D333#2': [('timberland', 3)],
}
# block A's band: the stretch's key -> brand (the two short stretches on the west stay white)
BAND_BRANDS = {
    'A359#0': 'lcwaikiki', 'A359#1': 'massimodutti', 'A347#0': 'zara',
    'A065#0': 'samsung', 'A065#1': 'apple', 'A065#2': 'mango', 'A065#3': 'bershka',
    'A184#0': 'hm', 'A176#0': 'uniqlo', 'A155#0': 'starbucks', 'A262#0': 'sephora',
}


def bearing(n):
    return (math.degrees(math.atan2(n[0], n[1])) + 360) % 360


def keyed(items, block_of, n_of, pos_of, tol=3.0):
    """'<block><bearing>#<k>': runs of one block facing the same way (within tol degrees) numbered
    left to right as seen from outside"""
    groups = []
    for it in items:
        b, br = block_of(it), bearing(n_of(it))
        for g in groups:
            if g['block'] == b and abs((br - g['br'] + 180) % 360 - 180) <= tol:
                g['items'].append(it)
                break
        else:
            groups.append(dict(block=b, br=br, items=[it]))
    out = {}
    for g in groups:
        n = n_of(g['items'][0])
        u = (-n[1], n[0])
        g['items'].sort(key=lambda it: pos_of(it)[0] * u[0] + pos_of(it)[1] * u[1])
        for k, it in enumerate(g['items']):
            key = f"{g['block']}{round(g['br']):03d}#{k}"
            while key in out:   # two groups rounding to the same bearing
                key += "'"
            out[key] = it
    return out


def portals(data, centre, towers):
    """the portals' heads -> [{block, c (on the facade plane), u (left to right), n (out), L}]"""
    CX, CY = centre
    res = []
    for blk, tris in data['portals'].items():
        u = unary_union([Polygon([(x + CX, -z + CY) for x, z in t]).buffer(0.01) for t in tris])
        cx, cy = towers[blk]['centre']
        for g in getattr(u, 'geoms', [u]):
            r = list(g.minimum_rotated_rectangle.exterior.coords)[:4]
            e = sorted([(r[i], r[(i + 1) % 4]) for i in range(4)], key=lambda s: -math.dist(*s))
            a, b = e[0]
            L = math.dist(a, b)
            ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            nx, ny = uy, -ux
            m = (g.centroid.x, g.centroid.y)
            if nx * (m[0] - cx) + ny * (m[1] - cy) < 0:
                nx, ny = -nx, -ny
            # the head box stands 0.10 m out of the facade plane on average (-0.02 .. 0.22)
            res.append(dict(block=blk, c=(m[0] - nx * 0.10, m[1] - ny * 0.10), u=(-ny, nx), n=(nx, ny), L=L - 0.02))
    return res


def runs_of(ps):
    faces = []
    for p in ps:
        for f in faces:
            q = f[0]
            if q['block'] == p['block'] and q['n'][0] * p['n'][0] + q['n'][1] * p['n'][1] > 0.999 and \
                    abs((p['c'][0] - q['c'][0]) * q['n'][0] + (p['c'][1] - q['c'][1]) * q['n'][1]) < 0.2:
                f.append(p)
                break
        else:
            faces.append([p])
    runs = []
    for f in faces:
        u = f[0]['u']
        f.sort(key=lambda p: p['c'][0] * u[0] + p['c'][1] * u[1])
        cur = [f[0]]
        for a, b in zip(f, f[1:]):
            if math.dist(a['c'], b['c']) < 4.6:
                cur.append(b)
            else:
                runs.append(cur)
                cur = [b]
        runs.append(cur)
    return runs


def band_stretches(data, centre):
    """straight stretches (over 4.5 m) of the outer edge of block A's upper band"""
    CX, CY = centre
    pts = [(x + CX, -z + CY) for x, z in data['band']]
    hull = shapely.geometry.polygon.orient(shapely.concave_hull(MultiPoint(pts), ratio=0.02), 1.0)
    ring = list(hull.exterior.coords)
    segs = []
    for a, b in zip(ring, ring[1:]):
        L = math.dist(a, b)
        if L < 0.01:
            continue
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        if segs and abs((ang - segs[-1]['ang'] + math.pi) % (2 * math.pi) - math.pi) < 0.03:
            segs[-1]['b'] = b
            segs[-1]['L'] += L
        else:
            segs.append(dict(a=a, b=b, ang=ang, L=L))
    mx, my = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    out = []
    for s in segs:
        if s['L'] < 4.5:
            continue
        a, b = s['a'], s['b']
        ux, uy = (b[0] - a[0]) / s['L'], (b[1] - a[1]) / s['L']
        n = (uy, -ux)   # right of a CCW ring: out of the ring's polygon
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        # the band is a ring round the podium: its outer edge looks away from the podium's middle
        if n[0] * (m[0] - mx) + n[1] * (m[1] - my) > 0:
            out.append(dict(block='A', a=a, b=b, n=n, c=m, L=s['L']))
    return out


def r3(v):
    return [round(x, 3) for x in v]


def main():
    cx = json.load(open(os.path.join(ROOT, 'src', 'model', 'complex.json')))
    towers = {t['key']: t for t in cx['towers']}
    data = json.load(open(os.path.join(ROOT, 'build', 'shopfronts.json')))
    runs = keyed(runs_of(portals(data, cx['site_centre'], towers)), lambda r: r[0]['block'], lambda r: r[0]['n'],
                 lambda r: r[0]['c'])
    band = keyed(band_stretches(data, cx['site_centre']), lambda s: 'A', lambda s: s['n'], lambda s: s['c'])
    if '--list' in sys.argv:
        for k, r in sorted(runs.items()):
            print(k, len(r), 'portals from', r3(r[0]['c']), '->', RUNS.get(k))
        for k, s in sorted(band.items()):
            print(k, 'band %.1f m' % s['L'], r3(s['c']), '->', BAND_BRANDS.get(k))
        return
    signs, used = [], set()
    for key, shops in RUNS.items():
        run = runs[key]
        assert sum(n for _, n in shops) == len(run), (key, len(run), shops)
        i = 0
        for brand, n in shops:
            assert brand in BRANDS and brand not in used, brand
            used.add(brand)
            ps = run[i:i + n]
            i += n
            first, last = ps[0], ps[-1]
            u, nn = first['u'], first['n']
            a = (first['c'][0] - u[0] * first['L'] / 2, first['c'][1] - u[1] * first['L'] / 2)
            b = (last['c'][0] + u[0] * last['L'] / 2, last['c'][1] + u[1] * last['L'] / 2)
            signs.append(dict(kind='sign', brand=brand, file=f'brands/{brand}.png', a=r3(a), b=r3(b), n=r3(nn),
                              z=round(sum(FRIEZE) / 2, 3), h=BRANDS[brand].get('h', SIGN_H), off=0.07, margin=0.3))
            # the poster: in the middle portal of three, the first of two
            p = ps[len(ps) // 2] if n == 3 else ps[0]
            c = p['c']
            signs.append(dict(kind='poster', brand=brand, file=f'brands/{brand}_banner.jpg',
                              a=r3((c[0] - u[0] * POSTER['half'], c[1] - u[1] * POSTER['half'])),
                              b=r3((c[0] + u[0] * POSTER['half'], c[1] + u[1] * POSTER['half'])),
                              n=r3(nn), z=POSTER['z'], h=POSTER['h'], off=POSTER['off'], margin=0.0))
    missing = sorted(set(runs) - set(RUNS))
    assert not missing, f'runs without shops: {missing}'
    for key, brand in BAND_BRANDS.items():
        s = band[key]
        assert brand in BRANDS and brand not in used, brand
        used.add(brand)
        signs.append(dict(kind='band', brand=brand, file=f'brands/{brand}_band.png', a=r3(s['a']), b=r3(s['b']),
                          n=r3(s['n']), z=BAND['z'], h=BAND['h'], off=BAND['off'], margin=1.2))
    path = os.path.join(ROOT, 'public', 'signs', 'signs.json')
    conf = json.load(open(path))
    conf['sets']['brands'] = signs
    conf['set'] = 'brands'
    # one sign per line: readable diffs
    body = ',\n'.join('      ' + json.dumps(s, ensure_ascii=False) for s in signs)
    text = json.dumps({k: v for k, v in conf.items() if k != 'sets'}, ensure_ascii=False, indent=2)[:-2]
    sets = ',\n'.join(
        f'    "{name}": [\n' + (body if name == 'brands' else ',\n'.join('      ' + json.dumps(s, ensure_ascii=False) for s in lst)) + '\n    ]'
        for name, lst in conf['sets'].items())
    open(path, 'w').write(text + ',\n  "sets": {\n' + sets + '\n  }\n}\n')
    print(len(used), 'brands,', sum(s['kind'] == 'sign' for s in signs), 'shop signs,',
          sum(s['kind'] == 'poster' for s in signs), 'posters,', sum(s['kind'] == 'band' for s in signs), 'on block A ->', path)
    unused = sorted(set(BRANDS) - used)
    if unused:
        print('not placed:', unused)


if __name__ == '__main__':
    main()
