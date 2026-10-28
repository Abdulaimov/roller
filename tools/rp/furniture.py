"""Furniture and sanitary ware as the sales book draws them -> the `furniture` of every flat in
blender/rp/plans.json (the items the viewer places, src/floor.js placeDrawn; formats as
tools/ab/furniture.py: c centre, w along the wall, d depth, f the way the front faces).

The sheets draw the furniture in thin black lines, the worktops and table tops in heavier black.
What is read (tools/rp/fsym.py: closed outlines drawn as one path, and the connected drawings):
  kitchen   the heavy outline 0.55-0.75 m deep along a wall; the hob (four rings) and the sink on it
  dining    the chairs (0.4-0.55 m squares) round a table: table and chairs as drawn
  sofa      in a living room the drawing 0.7-1.1 x 1.5-3.2 m; armchairs the 0.65-0.95 m squares
  tv        the slim box 0.1-0.5 x 1.0-2.6 m against a wall
  bed       the drawing 0.8-2.1 x 1.85-2.4 m in a bedroom; the head at the end against the wall;
            nightstands the small squares beside the head
  bath      0.6-0.9 x 1.4-1.95 m; shower tray 0.75-1.05 m square; toilet 0.3-0.55 x 0.5-0.85 m with
            curves (tank against the wall); basin 0.35-0.65 x 0.4-1.2 m with its bowl
A room gets its drawn pieces only when its main piece is found (the bed of a bedroom, the sofa of a
living room, the worktop of a kitchen, the WC or the bath/shower of a bathroom); otherwise the viewer
furnishes it itself, as before.
"""
import math
import os
import sys

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fsym  # noqa: E402

R3 = lambda v: round(float(v), 3)


def rect_poly(c, w, l, a):
    u = (math.cos(a), math.sin(a))
    v = (-u[1], u[0])
    return Polygon([(c[0] + u[0] * sl * l / 2 + v[0] * sw * w / 2, c[1] + u[1] * sl * l / 2 + v[1] * sw * w / 2)
                    for sl, sw in ((-1, -1), (1, -1), (1, 1), (-1, 1))])


def wall_front(c, w, l, a, solid, along=False):
    """the front direction of a piece against a wall: across its long side (or along it), pointing
    away from the nearer wall; and the distance to that wall"""
    u = (math.cos(a), math.sin(a))
    v = (-u[1], u[0])
    best = None
    dirs = [(u, l), ((-u[0], -u[1]), l)] if along else [(v, w), ((-v[0], -v[1]), w)]
    for n, depth in dirs:
        p = Point(c[0] + n[0] * (depth / 2 + 0.05), c[1] + n[1] * (depth / 2 + 0.05))
        dd = solid.distance(p) if not solid.is_empty else 9
        if best is None or dd < best[0]:
            best = (dd, n)
    n = best[1]
    return math.atan2(-n[1], -n[0]), best[0]


def read(pg, fr, plan, rect):
    rects = fsym.rects(pg, fr, rect)
    comps = fsym.components(fsym.segments(pg, fr, rect))
    solid = unary_union([Polygon(p).buffer(0) for p in plan['walls'] + plan['struct'] + plan['windows'] + plan['glazing'] + plan.get('parapets', [])])
    for c in comps:
        c['c'], c['w'], c['l'], c['a'] = fsym.mrr(c['shape'])
        # how much of its box the drawing fills (a bed with a desk stuck to it fills it badly)
        c['fill'] = c['shape'].area / max(c['w'] * c['l'], 1e-6) if c['shape'].geom_type in ('Polygon', 'MultiPolygon') else 0
        c['hull'] = c['geom'].convex_hull.area / max(c['w'] * c['l'], 1e-6)
    out_all = {}
    for ai, apt in enumerate(plan['apartments']):
        items = []
        for room in apt['rooms']:
            rp = Polygon(room['poly']).buffer(0.08)
            inside = lambda q: rp.contains(Point(*q['c']))
            R = [r for r in rects if inside(r)]
            C = [c for c in comps if inside(c) and c['l'] > 0.2]
            got = by_kind(room['kind'], R, C, solid, rp)
            items += fit_room(got, Polygon(room['poly']).buffer(0), solid)
        apt['furniture'] = items
        out_all[ai] = items
    return out_all


def footprint(it):
    t = it['type']
    if t == 'bed':
        return rect_poly(it['c'], it['w'], it['l'], it['f'])
    if t in ('dining', 'ctable', 'rug'):
        return rect_poly(it['c'], it['d'], it['w'], it['a'])
    if t == 'sofa':
        return unary_union([rect_poly((b[0], b[1]), b[3], b[2], b[6]) for b in it['boxes']])
    if t in ('toilet',):
        return rect_poly(it['c'], it['w'], it['d'], it['f'])
    return rect_poly(it['c'], it['d'], it['w'], it['f'] + math.pi / 2)   # w along the wall


def fit_room(items, room, solid):
    """what stands in the room only: a piece reaching into a wall is shrunk a little (the drawn
    symbols run a few centimetres into the walls), else left out (the viewer fills in for it);
    nightstands that hit a wall go; a table over the worktop moves off it; of two pieces on one spot
    the bigger stays"""
    inner = room.buffer(0.01).difference(solid)
    out = []
    for it in items:
        if it['type'] in ('rug', 'ctable'):
            out.append(it)
            continue
        if it['type'] == 'bed':
            it['stands'] = [s_ for s_ in it['stands'] if inner.contains(rect_poly((s_[0], s_[1]), s_[3], s_[2], it['f']))]
        if it['type'] == 'bed':   # (the viewer closes the seams between walls: a bed keeps 3 cm off)
            inner_ = inner
            inner = room.buffer(-0.03).difference(solid.buffer(0.03))
        ok = inner.contains(footprint(it))
        if not ok and it['type'] in ('bath', 'shower', 'kitchen', 'basin', 'toilet', 'bed', 'tv'):
            # off the wall behind it by up to 15 cm, then a little smaller
            keys = ('w', 'l') if it['type'] == 'bed' else ('w', 'd')
            n = (math.cos(it['f']), math.sin(it['f']))
            for k in range(0, 7):
                for m in (0.0, 0.03, 0.06, 0.09, 0.12, 0.15):
                    trial = dict(it, c=[R3(it['c'][0] + n[0] * m), R3(it['c'][1] + n[1] * m)], **{kk: R3(it[kk] * (1 - 0.025 * k)) for kk in keys})
                    if it['type'] == 'bed':
                        trial['stands'] = [[R3(x + n[0] * m), R3(y + n[1] * m), w_, d_] for x, y, w_, d_ in it['stands']]
                    if inner.contains(footprint(trial)):
                        it, ok = trial, True
                        break
                if ok:
                    break
        if not ok and it['type'] == 'dining':
            for k in range(1, 8):
                trial = dict(it, w=R3(it['w'] * (1 - 0.06 * k)), d=R3(max(0.7, it['d'] * (1 - 0.04 * k))))
                if inner.contains(footprint(trial)):
                    it, ok = trial, True
                    break
        if not ok and it['type'] not in ('armchair',):
            if it['type'] == 'bed':
                inner = inner_
            continue
        if it['type'] == 'bed':
            inner = inner_
            # (the viewer's headboard stands behind the drawn head: 6 cm off the wall for it)
            n = (math.cos(it['f']), math.sin(it['f']))
            it = dict(it, c=[R3(it['c'][0] + n[0] * 0.06), R3(it['c'][1] + n[1] * 0.06)], l=R3(it['l'] - 0.06))
        out.append(it)
    # overlaps: the smaller piece goes (a table: moved off the worktop if it can)
    keep = []
    for it in sorted(out, key=lambda q: -footprint(q).area):
        fp = footprint(it)
        clash = [q for q in keep if q['type'] not in ('rug',) and fp.intersection(footprint(q)).area > 0.02]
        if clash and it['type'] == 'ctable':
            continue
        if clash and it['type'] == 'dining':
            for step in (0.15, 0.3, 0.45):
                for q in clash:
                    qc = footprint(q).centroid
                    dx, dy = it['c'][0] - qc.x, it['c'][1] - qc.y
                    L = math.hypot(dx, dy) or 1
                    moved = dict(it, c=[R3(it['c'][0] + dx / L * step), R3(it['c'][1] + dy / L * step)],
                                 chairs=[[R3(x + dx / L * step), R3(y + dy / L * step), a] for x, y, a in it['chairs']])
                    if not any(footprint(moved).intersection(footprint(o)).area > 0.02 for o in keep):
                        it, clash = moved, []
                        break
                if not clash:
                    break
        if clash and it['type'] not in ('rug', 'ctable'):
            continue
        keep.append(it)
    return keep


def by_kind(kind, R, C, solid, rp):
    if kind == 'kitchen' or kind == 'living':
        out = []
        run = kitchen(R, C, solid) if kind == 'kitchen' else None
        if run:
            out.append(run)
        din = dining(R, solid)
        if din:
            out.append(din)
        if kind == 'living' and not run:
            run = kitchen(R, C, solid)   # a kitchen-living room (В: «меҳмонхона ба толори таомхӯрӣ»)
            if run:
                out.insert(0, run)
        if kind == 'living' or (kind == 'kitchen' and not run):
            liv = living(R, C, solid)
            if liv:
                out += liv
            elif kind == 'living':
                return []
        return out if (run or kind == 'living') else []
    if kind == 'bedroom':
        return bedroom(R, C, solid)
    if kind == 'bath':
        return bathroom(R, C, solid)
    return []


def kitchen(R, C, solid):
    tops = [r for r in R if r['thick'] and 0.5 <= r['w'] <= 0.78 and r['l'] >= 0.9]
    if not tops:
        # (a worktop drawn in thin lines: the long box with the hob on it)
        hobs = [c for c in C if c['curves'] >= 8 and 0.4 <= c['l'] <= 0.9]
        tops = [r for r in R if 0.52 <= r['w'] <= 0.75 and r['l'] >= 1.4 and any(r['poly'].buffer(0.05).contains(Point(*h['c'])) for h in hobs)]
    if not tops:
        return None
    t = max(tops, key=lambda r: r['l'])
    f, dw = wall_front(t['c'], t['w'], t['l'], t['a'], solid)
    if dw > 0.6:
        return None
    fx = (-math.sin(f), math.cos(f))   # the viewer's frame x of the run
    tp = t['poly'].buffer(0.05)
    on = [c for c in C if tp.contains(Point(*c['c'])) and c['l'] < 0.95]
    hob = next((c for c in on if c['curves'] >= 8 and 0.4 <= c['l'] <= 0.9), None)
    sink = next((c for c in on if c is not hob and c['curves'] >= 1 and 0.3 <= c['l'] <= 0.95), None)
    x = lambda c: (c['c'][0] - t['c'][0]) * fx[0] + (c['c'][1] - t['c'][1]) * fx[1]
    it = dict(type='kitchen', c=[R3(t['c'][0]), R3(t['c'][1])], w=R3(t['l']), d=R3(t['w']), f=R3(f),
              sink=R3(x(sink)) if sink else R3(-t['l'] / 4), bowls=1, hob=R3(x(hob)) if hob else R3(t['l'] / 4))
    return it


def dining(R, solid):
    chairs = [r for r in R if not r['thick'] and 0.36 <= r['w'] <= 0.58 and r['l'] <= 0.62]
    if len(chairs) < 3:
        return None
    # the biggest group of chairs within reach of each other
    groups = []
    for ch in chairs:
        for g in groups:
            if any(math.dist(ch['c'], o['c']) < 1.25 for o in g):
                g.append(ch)
                break
        else:
            groups.append([ch])
    g = max(groups, key=len)
    if len(g) < 3:
        return None
    pts = [o['c'] for o in g]
    cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ex, ey = max(xs) - min(xs), max(ys) - min(ys)
    a = 0.0 if ex >= ey else math.pi / 2
    L = max(ex, ey) + 0.15
    W = max(0.8, min(ex, ey) - 0.75)
    L = max(L - 0.0, 1.0)
    chairs_out = [[R3(p[0]), R3(p[1]), R3(math.atan2(cy - p[1], cx - p[0]))] for p in pts]
    return dict(type='dining', c=[R3(cx), R3(cy)], w=R3(min(L, 2.4)), d=R3(min(W, 1.1)), a=R3(a), chairs=chairs_out)


def living(R, C, solid):
    sofas = [c for c in C if 0.68 <= c['w'] <= 1.15 and 1.4 <= c['l'] <= 3.3 and len(c['faces']) >= 2 and (c['fill'] > 0.8 or c['hull'] > 0.9)]
    if not sofas:
        return None
    s = max(sofas, key=lambda c: c['l'])
    f, dw = wall_front(s['c'], s['w'], s['l'], s['a'], solid)
    if dw > 0.45:
        return None
    out = [sofa_item(s, f)]
    sp = rect_poly(s['c'], s['w'], s['l'], s['a']).buffer(0.05)
    for r in R:
        if 0.62 <= r['w'] <= 0.98 and r['l'] <= 1.0 and not sp.contains(Point(*r['c'])):
            # an armchair, turned to the sofa
            fa = math.atan2(s['c'][1] - r['c'][1], s['c'][0] - r['c'][0])
            out.append(dict(type='armchair', c=[R3(r['c'][0]), R3(r['c'][1])], w=R3(r['w']), d=R3(r['l']), f=R3(fa)))
    for r in R:
        if 0.08 <= r['w'] <= 0.5 and 1.0 <= r['l'] <= 2.6:
            ft, dt = wall_front(r['c'], r['w'], r['l'], r['a'], solid)
            if dt < 0.5:
                out.append(dict(type='tv', c=[R3(r['c'][0]), R3(r['c'][1])], w=R3(r['l']), d=R3(max(r['w'], 0.32)), f=R3(ft)))
                break
    # a rug and a coffee table between the sofa and what faces it
    n = (math.cos(f), math.sin(f))
    rc = (s['c'][0] + n[0] * (s['w'] / 2 + 0.95), s['c'][1] + n[1] * (s['w'] / 2 + 0.95))
    out.append(dict(type='rug', c=[R3(rc[0]), R3(rc[1])], w=R3(min(2.4, s['l'])), d=1.7, a=R3(s['a']), fit=0.96))
    out.append(dict(type='ctable', c=[R3(rc[0]), R3(rc[1])], w=0.9, d=0.55, a=R3(s['a']), h=0.4))
    return out


def sofa_item(s, f):
    """seat, back (against the wall) and two arms, as boxes for the viewer"""
    c, w, l, a = s['c'], s['w'], s['l'], s['a']
    u = (math.cos(a), math.sin(a))
    n = (math.cos(f), math.sin(f))   # front
    back_d, arm = 0.2, 0.14
    bc = (c[0] - n[0] * (w / 2 - back_d / 2), c[1] - n[1] * (w / 2 - back_d / 2))
    sc = (c[0] + n[0] * back_d / 2, c[1] + n[1] * back_d / 2)
    boxes = [[R3(sc[0]), R3(sc[1]), R3(l - 2 * arm), R3(w - back_d), 0, 0.45, R3(a), 'seat'],
             [R3(bc[0]), R3(bc[1]), R3(l), R3(back_d), 0, 0.85, R3(a), 'back']]
    for sg in (-1, 1):
        ac = (sc[0] + u[0] * sg * (l / 2 - arm / 2), sc[1] + u[1] * sg * (l / 2 - arm / 2))
        boxes.append([R3(ac[0]), R3(ac[1]), R3(arm), R3(w - back_d), 0, 0.6, R3(a), 'arm'])
    return dict(type='sofa', boxes=boxes)


def bedroom(R, C, solid):
    beds = [c for c in C if 0.8 <= c['w'] <= 2.15 and 1.85 <= c['l'] <= 2.45 and (c['fill'] > 0.88 or (c['hull'] > 0.75 and len(c['faces']) >= 3))]
    beds += [dict(c=r['c'], w=r['w'], l=r['l'], a=r['a'], faces=[1, 1]) for r in R if 0.8 <= r['w'] <= 2.15 and 1.85 <= r['l'] <= 2.45]
    # a bed drawn together with a desk, a rug or a wardrobe: grow it from its faces (the mattress,
    # the pillows, the turned-down blanket) while they make one clean bed-sized box
    for c in C:
        if c['fill'] > 0.88 or c['l'] < 1.8:
            continue
        faces = [f_ for f_ in c['faces'] if f_.area > 0.05]
        for seed in sorted(faces, key=lambda f_: -f_.area)[:4]:
            cur = seed
            grew = True
            while grew:
                grew = False
                for f_ in faces:
                    if f_.equals(cur) or cur.contains(f_.representative_point()) or cur.distance(f_) > 0.02:
                        continue
                    u = cur.union(f_)
                    cc, w, l, a = fsym.mrr(u)
                    if w <= 2.15 and l <= 2.45 and u.area / max(w * l, 1e-6) > 0.9:
                        cur, grew = u, True
            cc, w, l, a = fsym.mrr(cur)
            if 0.8 <= w <= 2.15 and 1.85 <= l <= 2.45 and cur.area / max(w * l, 1e-6) > 0.9:
                beds.append(dict(c=cc, w=w, l=l, a=a, faces=[1, 1]))
                break
    if not beds:
        return []
    out, used = [], []
    bedroom_ok = True
    for b in sorted(beds, key=lambda b: -b['w'] * b['l']):
        bp = rect_poly(b['c'], b['w'], b['l'], b['a'])
        if any(bp.intersects(o.buffer(-0.05)) for o in used):
            continue
        used.append(bp)
        f, dw = wall_front(b['c'], b['w'], b['l'], b['a'], solid, along=True)   # head -> foot
        if dw > 0.35:
            continue   # the head is not against a wall: not read with confidence
        n = (math.cos(f), math.sin(f))
        head = (b['c'][0] - n[0] * b['l'] / 2, b['c'][1] - n[1] * b['l'] / 2)
        side = (-n[1], n[0])
        stands = []
        for r in R:
            if r['l'] <= 0.62 and r['w'] >= 0.3 and math.dist(r['c'], head) < b['w'] / 2 + 0.6 and not bp.buffer(-0.02).contains(Point(*r['c'])):
                stands.append([R3(r['c'][0]), R3(r['c'][1]), R3(r['l']), R3(r['w'])])
        if not stands and b['w'] >= 1.3:
            for sg in (-1, 1):
                p = (head[0] + side[0] * sg * (b['w'] / 2 + 0.27) + n[0] * 0.22, head[1] + side[1] * sg * (b['w'] / 2 + 0.27) + n[1] * 0.22)
                stands.append([R3(p[0]), R3(p[1]), 0.48, 0.4])
        out.append(dict(type='bed', c=[R3(b['c'][0]), R3(b['c'][1])], w=R3(b['w']), l=R3(b['l']), f=R3(f), stands=stands[:2]))
    # two beds overlapping something else drawn as a bed: leave the room to the viewer
    return out


def bathroom(R, C, solid):
    out, taken = [], []

    def free(poly):
        return not any(poly.intersects(t.buffer(-0.03)) for t in taken)
    # baths and shower trays: the closed outlines (or clean drawings) of their size
    cands = [dict(c=r['c'], w=r['w'], l=r['l'], a=r['a'], poly=r['poly']) for r in R]
    cands += [dict(c=c['c'], w=c['w'], l=c['l'], a=c['a'], poly=rect_poly(c['c'], c['w'], c['l'], c['a'])) for c in C if c['fill'] > 0.9]
    for q in sorted(cands, key=lambda q: -q['w'] * q['l']):
        w, l = q['w'], q['l']
        if 0.6 <= w <= 0.92 and 1.4 <= l <= 1.98 and free(q['poly']):
            f, dw = wall_front(q['c'], w, l, q['a'], solid)
            if dw < 0.4:
                out.append(dict(type='bath', c=[R3(q['c'][0]), R3(q['c'][1])], w=R3(l), d=R3(w), f=R3(f), tap=1))
                taken.append(q['poly'])
        elif 0.75 <= w <= 1.08 and l <= 1.25 and free(q['poly']):
            f, dw = wall_front(q['c'], w, l, q['a'], solid)
            if dw < 0.4:
                out.append(dict(type='shower', c=[R3(q['c'][0]), R3(q['c'][1])], w=R3(l), d=R3(w), f=R3(f)))
                taken.append(q['poly'])
    # vanity tops with a basin: 0.4-0.65 deep, up to 1.6 long, against a wall
    for q in sorted(cands, key=lambda q: -q['l']):
        if 0.38 <= q['w'] <= 0.65 and 0.45 <= q['l'] <= 1.6 and free(q['poly']):
            f, dw = wall_front(q['c'], q['w'], q['l'], q['a'], solid)
            if dw < 0.3:
                out.append(dict(type='basin', c=[R3(q['c'][0]), R3(q['c'][1])], w=R3(q['l']), d=R3(q['w']), f=R3(f)))
                taken.append(q['poly'])
                break
    # WCs: a drawing of their size (tank and bowl), its long axis from the wall
    for c in C:
        if 0.3 <= c['w'] <= 0.56 and 0.45 <= c['l'] <= 0.82 and c['curves'] >= 2:
            f, dw = wall_front(c['c'], c['w'], c['l'], c['a'], solid, along=True)
            poly = rect_poly(c['c'], c['w'], c['l'], c['a'])
            if dw <= 0.3 and free(poly):
                out.append(dict(type='toilet', c=[R3(c['c'][0]), R3(c['c'][1])], w=R3(max(c['w'], 0.38)), d=R3(c['l'] + dw), f=R3(f)))
                taken.append(poly)
    # (else the bowl alone: an oval 0.3-0.5 x 0.4-0.65 m, its long axis from the wall)
    # (the bowls are drawn in curves that do not close exactly: the curves of a drawing that touch
    # are one shape)
    ovals = []
    for c in C:
        cur = [s_[0] for s_ in c['segs'] if s_[1]]
        if not cur:
            continue
        blob = unary_union([ln.buffer(0.02) for ln in cur])
        ovals += list(getattr(blob, 'geoms', [blob]))
    for g in ovals:
        cc, w, l, a = fsym.mrr(g)
        if not (0.27 <= w <= 0.52 and 0.36 <= l <= 0.72):
            continue
        f, dw = wall_front(cc, w, l, a, solid, along=True)
        if dw > 0.45:
            continue
        n = (math.cos(f), math.sin(f))
        back = (cc[0] - n[0] * (l / 2 + dw), cc[1] - n[1] * (l / 2 + dw))   # on the wall behind
        depth = l + dw
        c2 = (back[0] + n[0] * depth / 2, back[1] + n[1] * depth / 2)
        poly = rect_poly(c2, 0.42, depth, f)
        if not free(poly):
            continue
        out.append(dict(type='toilet', c=[R3(c2[0]), R3(c2[1])], w=0.4, d=R3(depth), f=R3(f)))
        taken.append(poly)
    if not any(it['type'] in ('toilet', 'bath', 'shower') for it in out):
        return []
    return out
