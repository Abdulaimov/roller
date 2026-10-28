"""The facade lighting at night, as the client's night renders show it (22.10.2026): warm uplights
washing up the brick piers between the window columns, from each band to the next; white light up
the white top's pilasters and the crown's fins; a white LED line along the top edge of every band and
cornice (the golden cornices, the dark base's band, the white top's cornice, the roof cornice); on
the glass tower a white line along every floor's band. Geometry only: quads a few centimetres in
front of the stone, in their own materials, which the viewer shows at dusk and at night
(src/night.js: the washes multiply the lit wall, the lines glow).
    'Night wash'   warm uplight (UV v 0 at the fixture, 1 at the top of the beam; u across it)
    'Night white'  white uplight (the same UVs)
    'Night line'   LED line
"""
import math

from shapely.geometry import Point, Polygon, box
from shapely.geometry.polygon import orient

from .config import level

WASH, WHITE, LINE = 'Night wash', 'Night white', 'Night line'


def wash(mb, F, s0, s1, z0, z1, off, mat=WASH):
    """an uplight's beam on face F from s0 to s1 along it, z0 (the fixture) to z1"""
    if s1 - s0 < 0.12 or z1 - z0 < 0.4:
        return
    a, b = F.p(s0, off), F.p(s1, off)
    mb.face([(*a, z0), (*b, z0), (*b, z1), (*a, z1)], mat, [(0, 0), (1, 0), (1, 1), (0, 1)])


def line(mb, F, s0, s1, z0, z1, off):
    if s1 - s0 < 0.05:
        return
    mb.quad_wall(F.p(s0, off), F.p(s1, off), z0, z1, LINE)


def ring_line(mb, poly, z0, z1, keep=lambda a, b: True):
    """an LED line round a polygon's outline (outward), on the edges `keep` accepts"""
    for g in getattr(poly, 'geoms', [poly]):
        if g.is_empty or g.geom_type != 'Polygon':
            continue
        pts = list(orient(g, 1.0).exterior.coords)
        for a, b in zip(pts, pts[1:]):
            if math.dist(a, b) > 0.05 and keep(a, b):
                mb.quad_wall(a, b, z0, z1, LINE)


# ---------------------------------------------------------------------------- the slab blocks

def piers(s0, s1, cuts, gap=0.06):
    """the stretches of [s0, s1] between the windows (cuts: (centre, width))"""
    out, at = [], s0
    for c, w in sorted(cuts):
        if c - w / 2 > at:
            out.append((at, c - w / 2))
        at = max(at, c + w / 2)
    if s1 > at:
        out.append((at, s1))
    return [(a + gap, b - gap) for a, b in out if b - a > 2 * gap + 0.15]


def slab_night(mb, b, zr):
    from . import slab as S
    Z = S.zones(b)
    lv = lambda f: level(f, b)
    for name, a, bb, layout, ax in S.faces():
        F = S.Face(a, bb, ax)
        # warm uplights up the brick, from the dark base's band, the golden cornices and to the white top
        for t0, t1, kind, opt in layout:
            if kind not in ('brick', 'pier') or opt.get('white'):
                continue
            s0, s1 = sorted((F.s(t0), F.s(t1)))
            s0, s1 = max(0.0, s0), min(F.L, s1)
            base = opt.get('base', 5)
            top = opt.get('top', Z['top_end'] if name == 'end' else Z['top'])
            breaks = [base] + [c for c in Z['cornices'] if base < c < top and name not in ('recess',)] + [top]
            cuts = [(F.s(c), 1.1 + 0.16) for c in opt.get('win', [])] + [(F.s(c), 0.9 + 0.1) for c in opt.get('glaze', [])]
            for fa, fb in zip(breaks, breaks[1:]):
                z0 = lv(fa) + (0.3 if fa == base else 0.55)
                z1 = lv(fb) - 0.35
                for p0, p1 in piers(s0, s1, cuts):
                    w = p1 - p0
                    if w > 1.1:     # a wide pier: a beam at each end (by the windows), not one flat wash
                        wash(mb, F, p0, p0 + 0.7, z0, z1, 0.03)
                        wash(mb, F, p1 - 0.7, p1, z0, z1, 0.03)
                    else:
                        wash(mb, F, p0, p1, z0, z1, 0.03)
        # white light up the white top's pilasters and the crown's fins
        spec = S.STREET_TOP if name == 'street' else S.COURT_TOP if name == 'court' else None
        if spec:
            for g in spec['groups']:
                for t in g:
                    if min(F.t_a, F.t_b) - 0.01 <= t <= max(F.t_a, F.t_b) + 0.01:
                        s = F.s(t)
                        wash(mb, F, s - 0.38, s + 0.38, lv(Z['top']) + 0.45, zr - 0.05, 0.34, WHITE)
            for (ta, tb), hgt in spec['crown']:
                sa_, sb_ = sorted((F.s(ta), F.s(tb)))
                n = max(2, round((sb_ - sa_) / 1.6) + 1)
                for k in range(n):
                    s = sa_ + (sb_ - sa_) * k / (n - 1)
                    wash(mb, F, s - 0.26, s + 0.26, zr + 0.86, zr + hgt, 0.33, WHITE)
        if name == 'end':
            for t in S.END_FINS:
                s = F.s(t)
                wash(mb, F, s - 0.24, s + 0.24, lv(Z['top_end']) + 0.45, zr + 3.4, 0.96, WHITE)
        # LED lines: the golden cornices, the white top's cornice, the courtyard panels' cornice
        segs = []
        for t0, t1, kind, opt in layout:
            if kind in ('pilaster', 'white'):
                continue
            s0, s1 = sorted((F.s(t0), F.s(t1)))
            s0, s1 = max(0.0, s0), min(F.L, s1)
            if segs and abs(segs[-1][1] - s0) < 0.02:
                segs[-1][1] = s1
            else:
                segs.append([s0, s1])
        if name not in ('recess', 'step1', 'step2', 'step3'):
            for c in Z['cornices']:
                for s0, s1 in segs:
                    line(mb, F, s0, s1, lv(c) + 0.31, lv(c) + 0.40, 0.432)
        if name not in ('end', 'recess', 'court'):
            for t0, t1, kind, opt in layout:
                if kind in ('pilaster', 'white', 'bay'):
                    continue
                s0, s1 = sorted((F.s(t0), F.s(t1)))
                line(mb, F, max(0.0, s0), min(F.L, s1), lv(Z['top']) + 0.31, lv(Z['top']) + 0.40, 0.432)
        if name == 'end':
            line(mb, F, 0.0, F.L, lv(Z['top_end']) + 0.31, lv(Z['top_end']) + 0.40, 0.432)
        if name == 'court':
            for t0, t1, kind, opt in layout:
                if kind == 'brick':
                    s0, s1 = sorted((F.s(t0), F.s(t1)))
                    zt = lv(opt.get('top', Z['top']))
                    line(mb, F, max(0, s0) - 0.1, min(F.L, s1) + 0.1, zt + 0.34, zt + 0.43, 0.462)
        # the dark base's band
        for t0, t1, kind, opt in layout:
            if kind not in ('brick', 'pier', 'gold', 'bay'):
                continue
            base = opt.get('base', 7 if kind in ('gold', 'bay') else 5)
            s0, s1 = sorted((F.s(t0), F.s(t1)))
            out = 0.3 + opt.get('proud', 0.0)
            line(mb, F, max(0, s0), min(F.L, s1), lv(base) + 0.14, lv(base) + 0.23, out + 0.012)
        # the corner bays' golden frames
        if name in ('step1', 'step2', 'step3'):
            for c in Z['bay_frames']:
                line(mb, F, -0.42, F.L + 0.42, lv(c) + 0.29, lv(c) + 0.37, 0.432)
    # the roof cornice
    out = S.outline()
    ring_line(mb, out.buffer(0.512, join_style='mitre'), zr + 0.66, zr + 0.76)


# ---------------------------------------------------------------------------- the glass tower

def tower_night(mb, b, plan, zr):
    from . import tower_a as T
    B = T.outline(plan)
    x0, y0, x1, y1 = B
    glass = box(x0, y0, x1, y1)
    outer = lambda a, c: not glass.buffer(0.2).contains(Point((a[0] + c[0]) / 2, (a[1] + c[1]) / 2))
    for f in range(3, b['floors'] + 1):
        skip = {}
        for lg, pair in T.LOGGIA_AT.get(f, []):
            if f == pair[1]:
                sp, _ = T.loggia_spans(B, f)
                for k, v in sp.items():
                    skip.setdefault(k, []).extend(v)
        bands = T.band_polygons(B, f, skip=skip)
        if bands.is_empty:
            continue
        z = level(f, b)
        ring_line(mb, bands.buffer(0.012, join_style='mitre'), z + T.BAND_H / 2 - 0.13, z + T.BAND_H / 2 - 0.04, outer)
    roof = T.band_polygons(B, 0, roof=True)
    if not roof.is_empty:
        ring_line(mb, roof.buffer(0.012, join_style='mitre'), zr + T.ROOF_BAND[1] - 0.13, zr + T.ROOF_BAND[1] - 0.04, outer)


def night_lights(mb, b, plan, zr):
    if b['style'] == 'glass':
        tower_night(mb, b, plan, zr)
    else:
        slab_night(mb, b, zr)
