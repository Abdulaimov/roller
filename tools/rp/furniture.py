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
NAMES = {'kitchen': ('Kitchen', 'Кухня', 'Ошхона'), 'living': ('Living room', 'Гостиная', 'Меҳмонхона')}
MAIN = {'bedroom': ('bed', 'sofa'), 'living': ('sofa', 'armchair'), 'kitchen': ('kitchen', 'sofa')}


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
        # (a sofa drawn with corners that do not close, or touching the radiator under the window
        # behind it, makes only small faces: for sofas, the box of all its lines too)
        hull = c['geom'].convex_hull
        if hull.area > 0.15 and c['shape'].area < 0.5 * hull.area:
            cc, w, l, a = fsym.mrr(c['geom'])
            fill = hull.area / max(w * l, 1e-6)
            c['alt'] = dict(c=cc, w=w, l=l, a=a, fill=fill, hull=fill, faces=c['faces'], curves=c['curves'])
    out_all = {}
    for ai, apt in enumerate(plan['apartments']):
        items = []
        for room in apt['rooms']:
            room.update(room.pop('sheet', {}))   # (read again: as the sheet signs it first)
            rp = Polygon(room['poly']).buffer(0.08)
            inside = lambda q: rp.contains(Point(*q['c']))
            R = [r for r in rects if inside(r)]
            C = [c for c in comps if inside(c) and c['l'] > 0.2]
            curves_in(R, [c for c in comps if inside(c)])
            # (what a piece stands against: the walls, and the room's own edge - a few partitions
            # are drawn as a single thin line that the plan's walls do not have)
            edge = solid if room['kind'] == 'bath' else solid.union(Polygon(room['poly']).buffer(0).boundary.buffer(0.03))
            got = by_kind(room['kind'], R, C, edge, rp)
            as_kind = next((it.pop('room_kind') for it in got if 'room_kind' in it), None)
            for it in got:
                it.pop('room_kind', None)
            fitted = fit_room(got, Polygon(room['poly']).buffer(0), solid)
            # (a room whose main piece did not fit keeps nothing of the drawing: the viewer
            # furnishes it whole, rather than leave a rug and a desk without the bed or the sofa)
            main = MAIN.get(as_kind or room['kind'])
            if main and not any(it['type'] in main for it in fitted):
                fitted = []
            if as_kind and fitted:
                # (the sheet signs it «Хонаи хоб», but draws a kitchen or a living room in it: the
                # flat's room count agrees with the drawing)
                room['sheet'] = {k: room[k] for k in ('kind', 'name', 'ru', 'tj')}
                room['kind'] = as_kind
                room['name'], room['ru'], room['tj'] = NAMES[as_kind]
            items += fitted
        # (one piece read twice - a kitchen run seen from the kitchen and from the living room open
        # to it: the bigger stays)
        keep = []
        for it in sorted(items, key=lambda q: -footprint(q).area):
            # (two desks meeting in an L, a corner of one inside the other - flat 182: the smaller goes)
            if it['type'] in ('kitchen', 'bed', 'sofa', 'bath', 'shower', 'dining', 'desk', 'tv') and \
                    any(o['type'] == it['type'] and footprint(o).intersection(footprint(it)).area > (0.005 if it['type'] == 'desk' else 0.05) for o in keep):
                continue
            keep.append(it)
        items = keep
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
    # (1.5 cm off the walls: the walls are the sheet's own lines now, the pieces drawn against them)
    inner = room.buffer(-0.015).difference(solid.buffer(0.015))
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
        if not ok and it['type'] in ('bath', 'shower', 'kitchen', 'basin', 'toilet', 'bed', 'tv', 'desk'):
            # off the wall behind it by up to 15 cm, then a little smaller
            keys = ('w', 'l') if it['type'] == 'bed' else ('w', 'd')
            n = (math.cos(it['f']), math.sin(it['f']))
            for k in range(0, 7):
                for m in (0.0, 0.03, 0.06, 0.09, 0.12, 0.15):
                    trial = dict(it, c=[R3(it['c'][0] + n[0] * m), R3(it['c'][1] + n[1] * m)], **{kk: R3(it[kk] * (1 - 0.025 * k)) for kk in keys})
                    if it['type'] == 'bed':
                        trial['stands'] = [[R3(x + n[0] * m), R3(y + n[1] * m), w_, d_] for x, y, w_, d_ in it['stands']]
                    if it['type'] == 'desk':
                        trial['chairs'] = [[R3(x + n[0] * m), R3(y + n[1] * m), a_] for x, y, a_ in it['chairs']]
                    if inner.contains(footprint(trial)):
                        it, ok = trial, True
                        break
                if ok:
                    break
        if not ok and it['type'] == 'sofa':
            # (off the wall behind it by up to 15 cm, the back drawn into the wall)
            n = (math.cos(it.get('f', 0)), math.sin(it.get('f', 0)))
            for m in (0.03, 0.06, 0.09, 0.12, 0.15):
                trial = dict(it, boxes=[[R3(b[0] + n[0] * m), R3(b[1] + n[1] * m)] + b[2:] for b in it['boxes']])
                if inner.contains(footprint(trial)):
                    it, ok = trial, True
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
            out += runs_of(run, R, C, solid)
        din = dining(R, solid, C)
        if din:
            out.append(din)
        if kind == 'living' and not run:
            run = kitchen(R, C, solid)   # a kitchen-living room (В: «меҳмонхона ба толори таомхӯрӣ»)
            if run:
                out = runs_of(run, R, C, solid) + out
        if kind == 'living' or (kind == 'kitchen' and not run):
            liv = living(R, C, solid, rp)
            if liv:
                out += liv + desks_tv(R, C, solid, out + liv)
            elif kind == 'living':
                return []
        return out if (run or kind == 'living') else []
    if kind == 'bedroom':
        out = bedroom(R, C, solid)
        if out:
            # (a sitting corner drawn beside the bed: a sofa, armchairs, a small table)
            out += seating(R, C, solid, rp, [footprint(it) for it in out])
            return out + desks_tv(R, C, solid, out)
        # no bed drawn: what the sheet draws there instead. A kitchen run (the room is the flat's
        # kitchen, signed «Хонаи хоб» on the sheet by mistake) or a sofa (a living room signed so,
        # with its armchairs and dining table; or a sofa bed with a desk)
        run = kitchen(R, C, solid)
        if run:
            out = runs_of(run, R, C, solid)
            din = dining(R, solid, C)
            out += [din] if din else []
            return [dict(it, room_kind='kitchen') for it in out]
        liv = living(R, C, solid, rp)
        if liv:
            din = dining(R, solid, C)
            out = liv + ([din] if din else [])
            if din or any(it['type'] == 'armchair' for it in liv):
                out = [dict(it, room_kind='living') for it in out]
            return out + desks_tv(R, C, solid, out)
        # (armchairs round a coffee table and a dining table, the sofa not read: a living room too)
        arms = [r for r in R if 0.62 <= r['w'] <= 0.98 and r['l'] <= 1.0]
        din = dining(R, solid, C)
        if len(arms) >= 2 and din:
            mx, my = sum(r['c'][0] for r in arms) / len(arms), sum(r['c'][1] for r in arms) / len(arms)
            out = [dict(type='armchair', c=[R3(r['c'][0]), R3(r['c'][1])], w=R3(r['w']), d=R3(r['l']),
                        f=R3(facing(r['c'], r['a'], (mx, my)))) for r in arms]
            for r in R:
                if 0.5 <= r['w'] <= 0.8 and 0.8 <= r['l'] <= 1.4 and math.dist(r['c'], (mx, my)) < 0.6:
                    out.append(dict(type='ctable', c=[R3(r['c'][0]), R3(r['c'][1])], w=R3(r['l']), d=R3(r['w']), a=R3(r['a']), h=0.4))
                    break
            out.append(din)
            out = [dict(it, room_kind='living') for it in out]
            return out + desks_tv(R, C, solid, out)
        return []
    if kind == 'bath':
        return bathroom(R, C, solid)
    return []


def marks(R, C):
    return [dict(c=c['c'], l=c['l'], curves=c['curves']) for c in C if c['l'] < 0.95] + \
        [dict(c=r['c'], l=r['l'], curves=r['curves']) for r in R if r.get('curves') and 0.3 <= r['w'] <= 0.7 and 0.4 <= r['l'] <= 0.95]


def curves_in(R, C0):
    """every closed box gets the number of curve pieces drawn in it (by any drawing in the room): a
    hob is a box with its four rings (16 and more), a sink a box with a rounded bowl. (The rings are
    small drawings of their own, or part of the worktop's one big drawing.)"""
    pts = [s_[0].interpolate(0.5, normalized=True) for c in C0 for s_ in c['segs'] if s_[1]]
    for r in R:
        q = r['poly'].buffer(-0.01)
        r['curves'] = sum(1 for p in pts if q.contains(p))


def is_hob(m):
    return m['curves'] >= 8 and 0.4 <= m['l'] <= 0.9


def kitchen(R, C, solid, runs=None):
    tops = [r for r in R if r['thick'] and 0.5 <= r['w'] <= 0.78 and r['l'] >= 0.9]
    # (a worktop outlined in heavy lines that do not make one closed path)
    tops += [dict(c=c['c'], w=c['w'], l=c['l'], a=c['a'], poly=rect_poly(c['c'], c['w'], c['l'], c['a']), thick=True)
             for c in C if c['thick'] >= 2 and 0.5 <= c['w'] <= 0.78 and c['l'] >= 0.9 and c['fill'] > 0.8]
    M = marks(R, C)
    hobs = [m for m in M if is_hob(m)]
    on_hob = lambda t: any(t['poly'].buffer(0.05).contains(Point(*h['c'])) for h in hobs)
    if not tops:
        # (a worktop drawn in thin lines: the long box with the hob on it)
        tops = [r for r in R if 0.52 <= r['w'] <= 0.75 and r['l'] >= 1.2 and on_hob(r)]
        tops += [dict(c=c['c'], w=c['w'], l=c['l'], a=c['a'], poly=rect_poly(c['c'], c['w'], c['l'], c['a']), thick=False)
                 for c in C if 0.52 <= c['w'] <= 0.75 and c['l'] >= 1.2 and c['fill'] > 0.7]
        tops = [t for t in tops if on_hob(t)]
    if not tops:
        # (the cabinets drawn one by one, 0.5-0.7 deep, side by side along a wall - a kitchen only
        # with the hob drawn on it: wardrobes are boxes on a wall too)
        tops = [t for t in modules(R, C, solid) if on_hob(t)]
    if runs is not None:
        # (the other runs of the kitchen: any worktop or row of cabinets against a wall)
        runs.extend(tops)
        runs.extend(modules(R, C, solid))
        runs.extend(r for r in R if 0.52 <= r['w'] <= 0.75 and r['l'] >= 1.0)
    if not tops:
        return None
    t = max(tops, key=lambda r: (on_hob(r), r['l']))
    return run_item(t, M, solid)


def run_item(t, M, solid):
    f, dw = wall_front(t['c'], t['w'], t['l'], t['a'], solid)
    if dw > 0.6:
        return None
    fx = (-math.sin(f), math.cos(f))   # the viewer's frame x of the run
    tp = t['poly'].buffer(0.05)
    on = [m for m in M if tp.contains(Point(*m['c']))]
    hob = next((m for m in on if is_hob(m)), None)
    sink = next((m for m in on if m is not hob and 1 <= m['curves'] < 16 and 0.3 <= m['l'] <= 0.95 and (hob is None or math.dist(m['c'], hob['c']) > 0.3)), None)
    x = lambda c: (c['c'][0] - t['c'][0]) * fx[0] + (c['c'][1] - t['c'][1]) * fx[1]
    it = dict(type='kitchen', c=[R3(t['c'][0]), R3(t['c'][1])], w=R3(t['l']), d=R3(t['w']), f=R3(f),
              sink=R3(x(sink)) if sink else R3(-t['l'] / 4), bowls=1, hob=R3(x(hob)) if hob else R3(t['l'] / 4))
    if not hob:
        it['hob'] = None   # (a run without the hob: cabinets only, its sink where drawn)
        if not sink:
            it['sink'] = None
    return it


def modules(R, C, solid):
    """kitchen cabinets drawn as separate boxes: each 0.5-0.7 m deep with its back on a wall; the
    boxes on one wall line, no more than 0.5 m apart (a cabinet drawn as the worktop alone), make a run (a box for each run, as a worktop)"""
    boxes = [dict(c=r['c'], w=r['w'], l=r['l'], a=r['a']) for r in R if not r['thick']]
    boxes += [dict(c=c['c'], w=c['w'], l=c['l'], a=c['a']) for c in C if c['fill'] > 0.85 and c['l'] <= 1.3]
    found = []
    for b in boxes:
        u = (math.cos(b['a']), math.sin(b['a']))
        v = (-u[1], u[0])
        for n, depth, along in ((u, b['l'], b['w']), ((-u[0], -u[1]), b['l'], b['w']), (v, b['w'], b['l']), ((-v[0], -v[1]), b['w'], b['l'])):
            if not (0.5 <= depth <= 0.72 and 0.3 <= along <= 1.3):
                continue
            # (the sheets draw some runs a few centimetres off the wall)
            back = Point(b['c'][0] - n[0] * (depth / 2 + 0.04), b['c'][1] - n[1] * (depth / 2 + 0.04))
            if solid.distance(back) > 0.18:
                continue
            t = (-n[1], n[0])   # along the wall
            off = b['c'][0] * n[0] + b['c'][1] * n[1] - depth / 2   # the back's line
            s0 = b['c'][0] * t[0] + b['c'][1] * t[1]
            found.append(dict(n=n, t=t, off=off, s0=s0 - along / 2, s1=s0 + along / 2, depth=depth))
    runs = []
    for q in sorted(found, key=lambda q: q['s0']):
        for r_ in runs:
            if abs(r_['n'][0] - q['n'][0]) < 0.1 and abs(r_['n'][1] - q['n'][1]) < 0.1 and abs(r_['off'] - q['off']) < 0.15 and q['s0'] <= r_['s1'] + 0.5:
                r_['s1'] = max(r_['s1'], q['s1'])
                r_['depth'] = max(r_['depth'], q['depth'])
                break
        else:
            runs.append(dict(q))
    out = []
    for r_ in runs:
        L = r_['s1'] - r_['s0']
        if L < 0.9:
            continue
        n, t, d = r_['n'], r_['t'], min(r_['depth'], 0.65)
        sm = (r_['s0'] + r_['s1']) / 2
        c = (n[0] * (r_['off'] + d / 2) + t[0] * sm, n[1] * (r_['off'] + d / 2) + t[1] * sm)
        a = math.atan2(t[1], t[0])
        out.append(dict(c=c, w=d, l=L, a=a, poly=rect_poly(c, d, L, a), thick=False))
    return out


def runs_of(run, R, C, solid):
    """the run read, and a second run on another wall (an L-shaped kitchen), cut back where it
    meets the first"""
    out = [run]
    tops = []
    kitchen(R, C, solid, tops)
    # (a clear 12 cm from the first run: the viewer sets each run back on its own wall's face)
    first = rect_poly(run['c'], run['d'], run['w'], run['f'] + math.pi / 2).buffer(0.12)
    for t in sorted(tops, key=lambda r: -r['l']):
        if t['poly'].centroid.distance(Point(*run['c'])) < 0.2:
            continue
        u = (math.cos(t['a']), math.sin(t['a']))
        # shorten it from the end that runs into the first run
        c, L = t['c'], t['l']
        for _ in range(30):
            if not rect_poly(c, t['w'], L, t['a']).intersects(first) or L < 0.9:
                break
            ends = [(c[0] + u[0] * L / 2, c[1] + u[1] * L / 2), (c[0] - u[0] * L / 2, c[1] - u[1] * L / 2)]
            sg = 1 if first.distance(Point(*ends[0])) < first.distance(Point(*ends[1])) else -1
            L -= 0.05
            c = (c[0] - u[0] * sg * 0.025, c[1] - u[1] * sg * 0.025)
        if L < 0.9 or rect_poly(c, t['w'], L, t['a']).intersects(first):
            continue
        it = run_item(dict(t, c=c, l=L, poly=rect_poly(c, t['w'], L, t['a'])), marks(R, C), solid)
        if it is None or wall_front(c, t['w'], L, t['a'], solid)[1] > 0.15:
            continue
        out.append(it)
        break
    return out


def desks_tv(R, C, solid, got):
    """a desk (0.45-0.68 deep, 0.9-1.9 long) against a wall, with the chair drawn at it; a TV
    stand (the slim box) - in a bedroom or a living room, where nothing read stands"""
    taken = [footprint(it) for it in got if it['type'] not in ('rug',)]
    free = lambda poly: not any(poly.intersects(t.buffer(-0.03)) for t in taken)
    chairs = [c for c in C if c['curves'] >= 6 and 0.35 <= c['w'] <= 0.7 and c['l'] <= 0.75]
    chairs += [dict(c=r['c']) for r in R if not r['thick'] and 0.36 <= r['w'] <= 0.58 and r['l'] <= 0.62]
    out = []
    for r in sorted(R, key=lambda r: -r['l']):
        if not (0.45 <= r['w'] <= 0.68 and 0.9 <= r['l'] <= 1.9) or not free(r['poly']):
            continue
        f, dw = wall_front(r['c'], r['w'], r['l'], r['a'], solid)
        if dw > 0.15:
            continue
        n = (math.cos(f), math.sin(f))
        front = (r['c'][0] + n[0] * (r['w'] / 2 + 0.3), r['c'][1] + n[1] * (r['w'] / 2 + 0.3))
        ch = [q for q in chairs if math.dist(q['c'], front) < 0.6 and not r['poly'].buffer(-0.03).contains(Point(*q['c']))][:2]
        out.append(dict(type='desk', c=[R3(r['c'][0]), R3(r['c'][1])], w=R3(r['l']), d=R3(r['w']), f=R3(f),
                        chairs=[[R3(q['c'][0]), R3(q['c'][1]), R3(f + math.pi)] for q in ch]))
        taken.append(r['poly'])
    if not any(it['type'] == 'tv' for it in got):
        for r in sorted(R, key=lambda r: r['w']):
            if 0.08 <= r['w'] <= 0.42 and 1.0 <= r['l'] <= 2.6 and free(r['poly']):
                ft, dt = wall_front(r['c'], r['w'], r['l'], r['a'], solid)
                if dt < 0.5:
                    out.append(dict(type='tv', c=[R3(r['c'][0]), R3(r['c'][1])], w=R3(r['l']), d=R3(max(r['w'], 0.32)), f=R3(ft)))
                    break
    return out


def drawn_table(g, C):
    """the table the chairs g stand round, as the sheet draws it: what is left of the drawing they
    belong to without them (flat 70's kitchen: a 0.7 x 1.8 m table against the wall, three chairs
    on one side and one at each end - the chairs' middle put the table on the chairs). None where it
    is not that clear"""
    chairs = unary_union([o['poly'] for o in g])
    for c in C:
        if sum(1 for o in g if c['geom'].distance(o['poly']) < 0.02) < max(3, len(g) - 1):
            continue
        rest = c['geom'].difference(chairs.buffer(0.03, join_style=2))
        if rest.is_empty or rest.length < 1.2:
            continue
        (tx, ty), tw, tl, ta = fsym.mrr(rest.convex_hull)
        if not (0.5 <= tw <= 1.3 and 0.7 <= tl <= 2.8):
            continue
        top = rect_poly((tx, ty), tw, tl, ta).buffer(-0.08)
        if any(top.contains(Point(*o['c'])) for o in g):
            continue
        return (tx, ty), tw, tl, ta
    return None


def dining(R, solid, C=()):
    # (not the hob or the sink: boxes of that size with curves in them; one box drawn twice, once)
    chairs = []
    for r in R:
        if not r['thick'] and 0.36 <= r['w'] <= 0.58 and r['l'] <= 0.62 and r.get('curves', 0) < 3 \
                and not any(math.dist(r['c'], o['c']) < 0.1 for o in chairs):
            chairs.append(r)
    if len(chairs) < 3:
        return None
    # the biggest group of chairs within reach of each other (across a table: up to 1.6 m)
    groups = []
    for ch in chairs:
        for g in groups:
            if any(math.dist(ch['c'], o['c']) < 1.6 for o in g):
                g.append(ch)
                break
        else:
            groups.append([ch])
    g = max(groups, key=len)
    if len(g) < 3:
        return None
    pts = [o['c'] for o in g]
    t = drawn_table(g, C)
    if t:
        (cx, cy), tw, tl, ta = t
        a = snap(ta)
        chairs_out = [[R3(p[0]), R3(p[1]), R3(facing(p, a, (cx, cy)))] for p in pts]
        return dict(type='dining', c=[R3(cx), R3(cy)], w=R3(min(tl, 2.4)), d=R3(min(tw, 1.1)), a=R3(a), chairs=chairs_out)
    cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ex, ey = max(xs) - min(xs), max(ys) - min(ys)
    a = 0.0 if ex >= ey else math.pi / 2
    L = max(ex, ey) + 0.15
    W = max(0.8, min(ex, ey) - 0.75)
    L = max(L - 0.0, 1.0)
    # (each chair square to the table: the side chairs face across it, the end ones along it)
    chairs_out = [[R3(p[0]), R3(p[1]), R3(facing(p, a, (cx, cy)))] for p in pts]
    return dict(type='dining', c=[R3(cx), R3(cy)], w=R3(min(L, 2.4)), d=R3(min(W, 1.1)), a=R3(a), chairs=chairs_out)


def snap(a):
    """an angle on the plan's axes (the sheets are drawn square to them)"""
    q = round(a / (math.pi / 2)) * (math.pi / 2)
    return q if abs(a - q) < math.radians(15) else a


def facing(c, a, to):
    """of the four ways square to a piece (its axes at a), the one that looks most towards `to`"""
    best = max((snap(a) + k * math.pi / 2 for k in range(4)),
               key=lambda f: math.cos(f) * (to[0] - c[0]) + math.sin(f) * (to[1] - c[1]))
    return math.atan2(math.sin(best), math.cos(best))


def seating(R, C, solid, room=None, taken=()):
    """sofas (up to two, as drawn), armchairs and the coffee table between them: each square to the
    room, the sofa's back to its wall (or, standing free, its front to the TV, the table or the
    middle of the room), the armchairs turned to the table"""
    free = lambda poly: not any(poly.intersects(t.buffer(-0.05)) for t in taken)
    # (cushions make faces; a sofa drawn with rounded corners that do not close has its curves)
    sofas = [c for c in C if 0.68 <= c['w'] <= 1.15 and 1.4 <= c['l'] <= 3.3
             and (len(c['faces']) >= 2 or c['curves'] >= 8) and (c['fill'] > 0.8 or c['hull'] > 0.9)]
    sofas += [c['alt'] for c in C if 'alt' in c and 0.68 <= c['alt']['w'] <= 1.15 and 1.4 <= c['alt']['l'] <= 3.3
              and (len(c['faces']) >= 2 or c['curves'] >= 8) and c['alt']['fill'] > 0.7]
    picked = []
    for c in sorted(sofas, key=lambda c: -c['l']):
        c = dict(c, a=snap(c['a']))
        poly = rect_poly(c['c'], c['w'], c['l'], c['a'])
        if free(poly) and not any(poly.intersects(rect_poly(o['c'], o['w'], o['l'], o['a']).buffer(-0.05)) for o in picked):
            picked.append(c)
        if len(picked) == 2:
            break
    if not picked:
        return []
    sp = unary_union([rect_poly(o['c'], o['w'], o['l'], o['a']).buffer(0.05) for o in picked])
    # the coffee table as drawn: a box 0.45-0.85 by 0.8-1.5 m in front of a sofa
    table = next((r for r in sorted(R, key=lambda r: min(math.dist(r['c'], o['c']) for o in picked))
                  if 0.45 <= r['w'] <= 0.85 and 0.8 <= r['l'] <= 1.5 and not sp.contains(Point(*r['c']))
                  and min(math.dist(r['c'], o['c']) for o in picked) < 2.2 and free(r['poly'])), None)
    tvs = [r for r in R if 0.08 <= r['w'] <= 0.42 and 1.0 <= r['l'] <= 2.6]
    out = []
    for o in picked:
        f, dw = wall_front(o['c'], o['w'], o['l'], o['a'], solid)
        if dw > 0.45:
            to = table['c'] if table else tvs[0]['c'] if tvs else ((room.centroid.x, room.centroid.y) if room is not None else None)
            if to is None:
                continue
            v = (-math.sin(o['a']), math.cos(o['a']))
            sg = 1 if (to[0] - o['c'][0]) * v[0] + (to[1] - o['c'][1]) * v[1] >= 0 else -1
            f = math.atan2(v[1] * sg, v[0] * sg)
        o['f'] = f
        out.append(sofa_item(o, f))
    if not out:
        return []
    main = picked[0]
    n = (math.cos(main['f']), math.sin(main['f']))
    if table:
        tc, tw, td, ta = table['c'], table['l'], table['w'], snap(table['a'])
    else:
        tc = (main['c'][0] + n[0] * (main['w'] / 2 + 0.75), main['c'][1] + n[1] * (main['w'] / 2 + 0.75))
        tw, td, ta = 0.9, 0.55, main['a']
    arms = [r for r in R if 0.62 <= r['w'] <= 0.98 and r['l'] <= 1.0]
    arms += [c for c in C if 0.62 <= c['w'] <= 0.98 and c['l'] <= 1.0 and c['fill'] > 0.8 and (c['faces'] or c['curves'] >= 6)
             and not any(math.dist(c['c'], r['c']) < 0.2 for r in arms)]
    for r in arms:
        if not sp.contains(Point(*r['c'])) and free(rect_poly(r['c'], r['w'], r['l'], r['a'])):
            # an armchair, square to the room, turned to the table
            out.append(dict(type='armchair', c=[R3(r['c'][0]), R3(r['c'][1])], w=R3(r['w']), d=R3(r['l']), f=R3(facing(r['c'], r['a'], tc))))
    # a rug under the table, square to the sofa
    out.append(dict(type='rug', c=[R3(tc[0]), R3(tc[1])], w=R3(min(2.4, main['l'])), d=1.7, a=R3(main['a']), fit=0.96))
    out.append(dict(type='ctable', c=[R3(tc[0]), R3(tc[1])], w=R3(tw), d=R3(td), a=R3(ta), h=0.4))
    return out


def living(R, C, solid, room=None):
    out = seating(R, C, solid, room)
    if not out:
        return None
    for r in sorted(R, key=lambda r: r['w']):
        if 0.08 <= r['w'] <= 0.42 and 1.0 <= r['l'] <= 2.6:
            ft, dt = wall_front(r['c'], r['w'], r['l'], r['a'], solid)
            if dt < 0.5:
                out.append(dict(type='tv', c=[R3(r['c'][0]), R3(r['c'][1])], w=R3(r['l']), d=R3(max(r['w'], 0.32)), f=R3(ft)))
                break
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
    return dict(type='sofa', boxes=boxes, f=R3(f))


def bedroom(R, C, solid):
    # (a single bed is drawn 0.9 x 1.8 m, some doubles 1.8 x 1.8)
    long_ok = lambda w, l: 1.75 <= l <= 2.45
    # (not a dining table: a drawing with chairs round it)
    chairs = [r for r in R if not r['thick'] and 0.36 <= r['w'] <= 0.58 and r['l'] <= 0.62]
    dining_ = lambda c: sum(1 for r in chairs if rect_poly(c['c'], c['w'], c['l'], c['a']).contains(Point(*r['c']))) >= 2
    C = [c for c in C if not dining_(c)]
    beds = [c for c in C if 0.8 <= c['w'] <= 2.15 and long_ok(c['w'], c['l']) and (c['fill'] > 0.88 or (c['hull'] > 0.75 and len(c['faces']) >= 3))]
    brs = [r for r in R if 0.8 <= r['w'] <= 2.15 and long_ok(r['w'], r['l'])]

    # (a box round a bed and the floor beside it is not a bed: one with a smaller bed inside goes)
    brs = [r for r in brs if not any(q is not r and q['w'] * q['l'] < 0.7 * r['w'] * r['l'] and r['poly'].buffer(-0.02).contains(Point(*q['c'])) for q in brs)]
    beds += [dict(c=r['c'], w=r['w'], l=r['l'], a=r['a'], faces=[1, 1], rect=True) for r in brs]
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
    # (a plain box of a single bed's size beside a double bed is a wardrobe - flat 182 had two read
    # as beds - unless its twin stands beside it: two single beds side by side)
    if any(b['w'] >= 1.3 for b in beds):
        twin = lambda b: any(o is not b and o['w'] < 1.3 and abs(o["l"] - b["l"]) < 0.15 and 0.5 < math.dist(o["c"], b["c"]) < 2.6 for o in beds)
        beds = [b for b in beds if not (b['w'] < 1.3 and not twin(b))]
    out, used = [], []
    double = False
    for b in sorted(beds, key=lambda b: (not b.get('rect'), -b['w'] * b['l'])):
        bp = rect_poly(b['c'], b['w'], b['l'], b['a'])
        if any(bp.intersects(o.buffer(-0.05)) for o in used):
            continue
        # (one double bed to a bedroom: flat 182's 45 m² bedroom had a second one read from its
        # sitting corner)
        if b['w'] >= 1.3 and double:
            continue
        double = double or b['w'] >= 1.3
        used.append(bp)
        if b['w'] > 0.9 * b['l']:
            # (a square bed: its head is the end with the pillows)
            b = pillows_first(b, C)
        f, dw = wall_front(b['c'], b['w'], b['l'], b['a'], solid, along=True)   # head -> foot
        if b.get('head') is not None:
            f = b['head']
            dw = solid.distance(Point(b['c'][0] - math.cos(f) * (b['l'] / 2 + 0.05), b['c'][1] - math.sin(f) * (b['l'] / 2 + 0.05)))
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


def pillows_first(b, C):
    """a bed about as wide as long: which of its four ends has the pillows (the small faces of its
    drawing) - the head; the bed turned so that its long axis runs from there"""
    comp = min(C, key=lambda c: math.dist(c['c'], b['c']), default=None)
    if comp is None or math.dist(comp['c'], b['c']) > 0.3:
        return b
    small = [f_ for f_ in comp['faces'] if 0.04 <= f_.area <= 0.45]
    if not small:
        return b
    best = None
    for k in range(4):
        a = b['a'] + k * math.pi / 2
        u = (math.cos(a), math.sin(a))
        half = (b['l'] if k % 2 == 0 else b['w']) / 2
        end = (b['c'][0] - u[0] * half, b['c'][1] - u[1] * half)   # the head end, the foot along +u
        n = sum(1 for f_ in small if f_.centroid.distance(Point(*end)) < 0.55)
        if best is None or n > best[0]:
            best = (n, a, k)
    n, a, k = best
    if n == 0:
        return b
    w, l = (b['w'], b['l']) if k % 2 == 0 else (b['l'], b['w'])
    return dict(b, a=a, w=w, l=l, head=a)


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
