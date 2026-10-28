"""Blocks Б, В, Г, Д (the slab blocks, one plan), their facades as the client renders show them.

The layout of each face was measured on the renders: render 1 (the street faces of Б and В, the
cameras fitted to the window and cornice rows, tools/ab/calib.py, and the picture put onto the
faces, tools/ab/posmap.mjs + unwrap.py), render 2 (the courtyard faces of Б and В and the west end
of Г), render 3 (the base, the shop fronts and the brick close up). Positions are plan metres
(plan x along the long faces, plan y along the ends), good to about 0.3 m on the street faces;
the courtyard faces follow render 2's sequence of panels fitted to the plan's stair recesses.

The faces are a simplified outline of the plan's facade line (its small jogs at the window
reveals are left out): the street face (+y) straight, the courtyard face (-y) with the two stair
hall recesses, the stepped corners and the ends. Each face is a list of vertical strips:
  brick      tan facing brick with punched windows (window columns at `win`), a dark graphite
             brick base below floor `base` (5 on the wings: the two floors over the shops; 7 in
             the middle and at the corners: four floors, a dark volume standing out)
  pier       narrow brick (as brick, no windows)
  screen     a dark perforated metal screen in a dark stone frame, from the shops to the roof
  glaze      tall narrow glazing, light glass, a mullion in the middle, a transom at each slab
  darkglass  a dark green glazed strip
  pilaster   white stone, standing out, from the shops past the roof
  white      a white stone panel with windows, full height (the courtyard face)
  bay        the corner bays: blue glass with golden frames (on the corner steps)
  gold       golden stone (the corner piers)
Over the floors the white top (floor `top` up): white stone with pilasters in groups and narrow
windows between them; the screens, the dark strips and the bays run on through it; the wings'
pilaster groups rise past the roof as a crown. Golden stone cornices at two floors cross the
brick, the screens and the glazing (not the white pilasters or panels); a dark stone cornice
over the dark base; a white cornice under the white top; a white roof cornice and parapet.
"""
import math

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from .config import BLOCKS, SLAB, height, level

STREET_Y = 12.875
COURT_Y = -12.875
END_X = 32.17
STEP1_X, STEP2_X = 27.89, 29.95
STEP1_Y, STEP2_Y = 10.65, 7.72      # +y corners; the -y corners at -10.65 and -7.82
STEP2_YS = -7.82
RECESS = (7.54, 12.4)               # the stair hall recesses of the courtyard face, |x|
RECESS_Y = -10.7

# ---------------------------------------------------------------------------- layouts
# (t0, t1, kind, options); t runs left to right as seen from outside the face

STREET = [   # render 1, plan x from +27.89 to -27.89 (seen from the street: +x on the left)
    (27.89, 27.6, 'pier', {'base': 7}),
    (27.6, 25.6, 'screen', {}),
    (25.6, 25.2, 'pier', {}),
    (25.2, 21.8, 'brick', {'win': [23.5]}),
    (21.8, 20.2, 'glaze', {}),
    (20.2, 19.8, 'pier', {}),
    (19.8, 17.6, 'screen', {}),
    (17.6, 17.2, 'pier', {}),
    (17.2, 15.6, 'glaze', {}),
    (15.6, 11.9, 'brick', {'win': [13.6]}),
    (11.9, 10.4, 'darkglass', {}),
    (10.4, 9.3, 'pilaster', {}),
    (9.3, 7.5, 'darkglass', {}),
    (7.5, 4.7, 'screen', {}),
    (4.7, -0.6, 'brick', {'win': [3.45, 0.9], 'base': 7, 'proud': 0.35}),
    (-0.6, -2.6, 'screen', {}),
    (-2.6, -7.7, 'brick', {'win': [-4.05, -6.45], 'base': 7, 'proud': 0.35}),
    (-7.7, -8.8, 'darkglass', {}),
    (-8.8, -10.1, 'pilaster', {}),
    (-10.1, -11.6, 'darkglass', {}),
    (-11.6, -11.8, 'pier', {'white': True}),
    (-11.8, -14.1, 'screen', {}),
    (-14.1, -17.9, 'brick', {'win': [-15.95]}),
    (-17.9, -19.1, 'darkglass', {}),
    (-19.1, -21.7, 'screen', {}),
    (-21.7, -22.6, 'darkglass', {}),
    (-22.6, -26.3, 'brick', {'win': [-24.9]}),
    (-26.3, -27.89, 'darkglass', {}),
]
# the white top of the street face: pilasters (centre x) in groups (narrow windows between the
# pilasters of a group) and the strips that run on through it (render 1, z 69-82)
STREET_TOP = {
    'groups': [[24.6, 22.9, 21.4, 19.75], [16.5, 14.9, 13.25, 11.75], [4.4, 2.0, -0.4], [-3.25, -5.5, -7.9],
               [-15.5, -17.1, -18.5, -20.0], [-23.25, -24.75, -26.4]],
    # the crown (render 1): a comb of separate white fins over each wing, 4.5 m past the roof on the
    # +x wing and 4.0 m on the -x wing; the middle has the heavy roof cornice only
    'crown': [((25.4, 11.2), 4.5), ((-12.6, -27.2), 4.0)],
}
COURT = [    # render 2 (seen from the courtyard: -x on the left; its camera fitted to B's window rows
    # with the stair recess at -12.4..-7.54 = the white panel), symmetric about x = 0
    (-27.89, -27.3, 'screen', {}),
    (-27.3, -13.2, 'brick', {'win': [-25.4, -22.9, -20.4, -14.6], 'glaze': [-17.2]}),
    (-13.2, -12.4, 'screen', {}),
    (-7.54, -6.8, 'darkglass', {}),
    (-6.8, -1.0, 'brick', {'win': [-5.0, -2.6], 'base': 7, 'top': 20}),
    (-1.0, 1.0, 'screen', {}),
    (1.0, 6.8, 'brick', {'win': [2.6, 5.0], 'base': 7, 'top': 20}),
    (6.8, 7.54, 'darkglass', {}),
    (12.4, 13.2, 'screen', {}),
    (13.2, 27.3, 'brick', {'win': [14.6, 20.4, 22.9, 25.4], 'glaze': [17.2]}),
    (27.3, 27.89, 'screen', {}),
]
COURT_TOP = {'groups': [[-25.4, -23.9, -22.4, -20.9], [-17.9, -16.4, -14.9], [-5.6, -4.1, -2.6], [2.6, 4.1, 5.6],
                        [14.9, 16.4, 17.9], [20.9, 22.4, 23.9, 25.4]], 'crown': []}
END = [      # render 2 (Г's west end) and the plan's four end windows; plan y, symmetric
    (7.72, 6.67, 'screen', {}),
    (6.67, 5.56, 'pier', {}),
    (5.56, 4.06, 'glaze', {'white_frame': True}),
    (4.06, 2.07, 'pier', {}),
    (2.07, 0.58, 'glaze', {'white_frame': True}),
    (0.58, -1.6, 'pier', {}),
    (-1.6, -3.1, 'glaze', {'white_frame': True}),
    (-3.1, -4.39, 'pier', {}),
    (-4.39, -5.89, 'glaze', {'white_frame': True}),
    (-5.89, -6.77, 'pier', {}),
    (-6.77, -7.82, 'screen', {}),
]
# the white top of the ends: one floor deeper, deep fins at the piers with balconies between
END_FINS = [6.1, 3.06, -0.5, -3.75, -6.3]

# ---------------------------------------------------------------------------- the faces

def faces():
    """[(name, a, b, layout, layout t range is along a->b)]: every face of the outline, CCW, with
    its strips. a, b are plan points; t along a face is the plan coordinate the layout uses."""
    F = []
    X1, X2, E = STEP1_X, STEP2_X, END_X
    # street face (+y): from x=+27.89 to -27.89
    F.append(('street', (X1, STREET_Y), (-X1, STREET_Y), STREET, 'x'))
    # -x/+y corner steps, the -x end, the -x/-y corner steps
    F.append(('step1', (-X1, STREET_Y), (-X1, STEP1_Y), [(STREET_Y, STEP1_Y, 'bay', {})], 'y'))
    F.append(('step2', (-X1, STEP1_Y), (-X2, STEP1_Y), [(-X1, -X2, 'bay', {})], 'x'))
    F.append(('step3', (-X2, STEP1_Y), (-X2, STEP2_Y), [(STEP1_Y, STEP2_Y, 'gold', {})], 'y'))
    F.append(('step4', (-X2, STEP2_Y), (-E, STEP2_Y), [(-X2, -E, 'screen', {})], 'x'))
    F.append(('end', (-E, STEP2_Y), (-E, STEP2_YS), END, 'y'))
    F.append(('step4', (-E, STEP2_YS), (-X2, STEP2_YS), [(-E, -X2, 'screen', {})], 'x'))
    F.append(('step3', (-X2, STEP2_YS), (-X2, -STEP1_Y), [(STEP2_YS, -STEP1_Y, 'gold', {})], 'y'))
    F.append(('step2', (-X2, -STEP1_Y), (-X1, -STEP1_Y), [(-X2, -X1, 'bay', {})], 'x'))
    F.append(('step1', (-X1, -STEP1_Y), (-X1, COURT_Y), [(-STEP1_Y, COURT_Y, 'bay', {})], 'y'))
    # courtyard face (-y) with the two recesses
    r0, r1 = RECESS
    F.append(('court', (-X1, COURT_Y), (-r1, COURT_Y), [s for s in COURT if s[1] <= -r1 + 1e-6], 'x'))
    F.append(('recess', (-r1, COURT_Y), (-r1, RECESS_Y), [(COURT_Y, RECESS_Y, 'white', {'win': [], 'flat': True})], 'y'))
    F.append(('recess', (-r1, RECESS_Y), (-r0, RECESS_Y), [(-r1, -r0, 'white', {'win': [-(r0 + r1) / 2], 'wide': 2.6})], 'x'))
    F.append(('recess', (-r0, RECESS_Y), (-r0, COURT_Y), [(RECESS_Y, COURT_Y, 'white', {'win': [], 'flat': True})], 'y'))
    F.append(('court', (-r0, COURT_Y), (r0, COURT_Y), [s for s in COURT if s[0] >= -r0 - 1e-6 and s[1] <= r0 + 1e-6], 'x'))
    F.append(('recess', (r0, COURT_Y), (r0, RECESS_Y), [(COURT_Y, RECESS_Y, 'white', {'win': [], 'flat': True})], 'y'))
    F.append(('recess', (r0, RECESS_Y), (r1, RECESS_Y), [(r0, r1, 'white', {'win': [(r0 + r1) / 2], 'wide': 2.6})], 'x'))
    F.append(('recess', (r1, RECESS_Y), (r1, COURT_Y), [(RECESS_Y, COURT_Y, 'white', {'win': [], 'flat': True})], 'y'))
    F.append(('court', (r1, COURT_Y), (X1, COURT_Y), [s for s in COURT if s[0] >= r1 - 1e-6], 'x'))
    # +x/-y corner steps, the +x end, the +x/+y corner steps
    F.append(('step1', (X1, COURT_Y), (X1, -STEP1_Y), [(COURT_Y, -STEP1_Y, 'bay', {})], 'y'))
    F.append(('step2', (X1, -STEP1_Y), (X2, -STEP1_Y), [(X1, X2, 'bay', {})], 'x'))
    F.append(('step3', (X2, -STEP1_Y), (X2, STEP2_YS), [(-STEP1_Y, STEP2_YS, 'gold', {})], 'y'))
    F.append(('step4', (X2, STEP2_YS), (E, STEP2_YS), [(X2, E, 'screen', {})], 'x'))
    F.append(('end', (E, STEP2_YS), (E, STEP2_Y), END, 'y'))
    F.append(('step4', (E, STEP2_Y), (X2, STEP2_Y), [(E, X2, 'screen', {})], 'x'))
    F.append(('step3', (X2, STEP2_Y), (X2, STEP1_Y), [(STEP2_Y, STEP1_Y, 'gold', {})], 'y'))
    F.append(('step2', (X2, STEP1_Y), (X1, STEP1_Y), [(X2, X1, 'bay', {})], 'x'))
    F.append(('step1', (X1, STEP1_Y), (X1, STREET_Y), [(STEP1_Y, STREET_Y, 'bay', {})], 'y'))
    return F


def outline():
    """the simplified outline (CCW) the faces run along"""
    pts = []
    for name, a, b, lay, ax in faces():
        if not pts or math.dist(pts[-1], a) > 1e-6:
            pts.append(a)
        pts.append(b)
    if math.dist(pts[0], pts[-1]) < 1e-6:
        pts.pop()
    p = Polygon(pts)
    return p if p.exterior.is_ccw else Polygon(pts[::-1])


# ---------------------------------------------------------------------------- floors and zones

def zones(block):
    """the floors where things change on this block (22 floors: Б, Г, Д; 20: В)"""
    N = block['floors']
    if N >= 22:
        return dict(N=N, top=N - 3, top_end=N - 4, cornices=(11, 17), bay_frames=(7, 11, 17, N - 1))
    return dict(N=N, top=N - 3, top_end=N - 4, cornices=(10, 15), bay_frames=(7, 10, 15, N - 1))


def look_of(block, f):
    """everything about floor f that changes its facade (floors alike share their meshes)"""
    z = zones(block)
    return ('slab', z['N'], f < 5, f < 7, f in (5, 7), f in z['cornices'], f >= z['top'], f == z['top'],
            f >= z['top_end'], f == z['top_end'], f in z['bay_frames'], f == z['N'], f == 20, f >= 20)


# ---------------------------------------------------------------------------- building blocks

class Face:
    """a straight face from a to b (plan), outward normal n; t is the layout coordinate"""

    def __init__(self, a, b, ax):
        self.a, self.b, self.ax = a, b, ax
        L = math.dist(a, b)
        self.L = L
        self.u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        self.n = (self.u[1], -self.u[0])          # outward for a CCW ring
        self.rot = math.atan2(self.u[1], self.u[0])
        self.t_a = a[0] if ax == 'x' else a[1]
        self.t_b = b[0] if ax == 'x' else b[1]

    def s(self, t):
        """distance along the face for layout coordinate t"""
        return (t - self.t_a) / (self.t_b - self.t_a) * self.L

    def p(self, s, off=0.0):
        return (self.a[0] + self.u[0] * s + self.n[0] * off, self.a[1] + self.u[1] * s + self.n[1] * off)


def slab_box(mb, F, s0, s1, off0, off1, z0, z1, mat, top=True, bottom=False):
    """a box on face F from s0 to s1 along it, off0..off1 out of the face line, z0..z1"""
    if s1 - s0 < 0.005 or off1 - off0 < 0.002 or z1 - z0 < 0.002:
        return
    c = F.p((s0 + s1) / 2, (off0 + off1) / 2)
    mb.box(c[0], c[1], z0, s1 - s0, off1 - off0, z1 - z0, mat, rot=F.rot, top=top, bottom=bottom)


def wall(mb, F, s0, s1, z0, z1, mat, off=0.0, u0=None):
    """the face of the wall from s0 to s1 (outward, UVs in metres along the face)"""
    if s1 - s0 < 0.005 or z1 - z0 < 0.005:
        return
    mb.quad_wall(F.p(s0, off), F.p(s1, off), z0, z1, mat, u0=s0 if u0 is None else u0)


def punched(mb, F, s0, s1, h, mat, wins, sill, head, frame='Frame light', glass='Window glass', reveal=0.2, stone=None):
    """a wall strip from s0 to s1 with punched windows at the centres in `wins` (s, width)"""
    cuts = sorted((c - w / 2, c + w / 2) for c, w in wins if s0 < c < s1)
    at = s0
    for w0, w1 in cuts:
        wall(mb, F, at, w0, 0.0, h, mat)
        at = w1
    wall(mb, F, at, s1, 0.0, h, mat)
    for w0, w1 in cuts:
        wall(mb, F, w0, w1, 0.0, sill, mat)
        wall(mb, F, w0, w1, head, h, mat)
        # reveals
        a0, a1 = F.p(w0), F.p(w1)
        i0, i1 = F.p(w0, -reveal), F.p(w1, -reveal)
        mb.quad_wall(a0, i0, sill, head, mat)
        mb.quad_wall(i1, a1, sill, head, mat)
        mb.face([(*i0, head), (*i1, head), (*a1, head), (*a0, head)], mat)   # the soffit, facing down
        mb.face([(*a0, sill), (*a1, sill), (*i1, sill), (*i0, sill)], mat)   # the sill, facing up
        # glass, the frame and a mullion
        mb.quad_wall(i0, i1, sill, head, glass, u0=w0)
        cm = (w0 + w1) / 2
        for ss, ww in ((w0 + 0.04, 0.08), (w1 - 0.04, 0.08), (cm, 0.07)):
            slab_box(mb, F, ss - ww / 2, ss + ww / 2, -reveal + 0.005, -reveal + 0.07, sill, head, frame)
        slab_box(mb, F, w0, w1, -reveal + 0.005, -reveal + 0.07, sill, sill + 0.07, frame)
        slab_box(mb, F, w0, w1, -reveal + 0.005, -reveal + 0.07, head - 0.07, head, frame)
        slab_box(mb, F, w0, w1, -reveal + 0.005, -reveal + 0.07, sill + (head - sill) * 0.62, sill + (head - sill) * 0.62 + 0.05, frame)
        # a stone sill and a lintel
        if stone:
            slab_box(mb, F, w0 - 0.08, w1 + 0.08, -0.02, 0.06, sill - 0.08, sill, stone)
            slab_box(mb, F, w0 - 0.06, w1 + 0.06, -0.02, 0.03, head, head + 0.14, stone)


def glazing(mb, F, s0, s1, z0, z1, glass, frame, mullions=1, transom=None, depth=0.12, white_frame=False):
    """a glazed strip set `depth` back, framed, with mullions and a transom at the slab"""
    if s1 - s0 < 0.2:
        return
    fr = 'Stone white' if white_frame else frame
    wall(mb, F, s0, s1, z0, z1, glass, off=-depth)
    for s in [s0 + 0.04, s1 - 0.04] + [s0 + (s1 - s0) * (k + 1) / (mullions + 1) for k in range(mullions)]:
        slab_box(mb, F, s - 0.04, s + 0.04, -depth, -depth + 0.08, z0, z1, frame)
    slab_box(mb, F, s0, s1, -depth, -depth + 0.1, z0, z0 + 0.12, frame)
    if transom:
        slab_box(mb, F, s0, s1, -depth, -depth + 0.08, transom, transom + 0.06, frame)
    # the reveals of the strip
    for s in (s0, s1):
        p0, p1 = F.p(s), F.p(s, -depth)
        mb.quad_wall(p0, p1, z0, z1, fr) if s == s0 else mb.quad_wall(p1, p0, z0, z1, fr)
    if white_frame:
        slab_box(mb, F, s0 - 0.12, s0 + 0.02, -0.02, 0.1, z0, z1, 'Stone white')
        slab_box(mb, F, s1 - 0.02, s1 + 0.12, -0.02, 0.1, z0, z1, 'Stone white')


def screen(mb, F, s0, s1, z0, z1):
    """the dark perforated screen in a dark stone frame (UVs: metres, for the viewer's pattern)"""
    if s1 - s0 < 0.2:
        return
    fr = 0.12
    wall(mb, F, s0 + fr, s1 - fr, z0, z1, 'Screen dark', off=-0.08)
    slab_box(mb, F, s0, s0 + fr, -0.08, 0.04, z0, z1, 'Stone dark')
    slab_box(mb, F, s1 - fr, s1, -0.08, 0.04, z0, z1, 'Stone dark')


# ---------------------------------------------------------------------------- one floor

def strip_zone(kind, opt, f, Z, face):
    """'base', 'body' or 'top' for this strip on floor f"""
    top = opt.get('top', Z['top_end'] if face == 'end' else Z['top'])
    if f >= top:
        return 'top'
    base = opt.get('base', 5)
    if f < base:
        return 'base'
    return 'body'


def floor_facade(mb, block, f, h):
    """the walls of floor f (z = 0 at its floor level)"""
    Z = zones(block)
    sill, head = 0.9, 2.55
    for name, a, b, layout, ax in faces():
        F = Face(a, b, ax)
        top_spec = STREET_TOP if name == 'street' else COURT_TOP if name == 'court' else None
        top_pils = []
        if top_spec:
            for g in top_spec['groups']:
                top_pils += [F.s(t) for t in g if min(F.t_a, F.t_b) - 0.01 <= t <= max(F.t_a, F.t_b) + 0.01]
        for t0, t1, kind, opt in layout:
            s0, s1 = sorted((F.s(t0), F.s(t1)))
            s0, s1 = max(0.0, s0), min(F.L, s1)
            if s1 - s0 < 0.02:
                continue
            zone = strip_zone(kind, opt, f, Z, 'end' if name == 'end' else name)
            wins = [(F.s(c), 1.1) for c in opt.get('win', [])]
            if kind in ('brick', 'pier'):
                if zone == 'top' and not (name == 'end' and kind == 'pier'):
                    white_top(mb, F, s0, s1, h, f, Z, name, top_pils, opt)
                    continue
                if name == 'end' and zone == 'top' and kind == 'pier':
                    wall(mb, F, s0, s1, 0.0, h, 'Stone white')
                    continue
                mat = 'Stone white' if opt.get('white') else 'Brick dark' if zone == 'base' else 'Brick tan'
                proud = opt.get('proud', 0.0) if zone == 'base' else 0.0
                if proud:
                    # the dark volume standing out of the face: its ends, and its front with windows
                    mb.quad_wall(F.p(s0), F.p(s0, proud), 0.0, h, mat)
                    mb.quad_wall(F.p(s1, proud), F.p(s1), 0.0, h, mat)
                    Fp = Face(F.p(0, proud), F.p(F.L, proud), ax)
                    Fp.t_a, Fp.t_b = F.t_a, F.t_b
                    punched(mb, Fp, s0, s1, h, mat, wins if kind == 'brick' else [], sill, head, stone='Stone dark', reveal=0.25)
                else:
                    punched(mb, F, s0, s1, h, mat, wins if kind == 'brick' else [], sill, head,
                            stone='Stone dark' if zone == 'base' else 'Stone gold')
                for c in opt.get('glaze', []):
                    sc = F.s(c)
                    glazing(mb, F, sc - 0.45, sc + 0.45, 0.0, h, 'Glass light', 'Frame dark', mullions=0, transom=None)
            elif kind == 'white':
                ww = opt.get('wide', 1.1)
                if opt.get('flat'):
                    wall(mb, F, s0, s1, 0.0, h, 'Stone white')
                else:
                    punched(mb, F, s0, s1, h, 'Stone white', [(c, ww) for c, _ in wins], sill, head + 0.15,
                            frame='Frame dark', stone=None, reveal=0.22)
            elif kind == 'screen':
                screen(mb, F, s0, s1, 0.0, h)
            elif kind == 'glaze':
                if zone == 'top' and name != 'end':
                    white_top(mb, F, s0, s1, h, f, Z, name, top_pils, opt)
                    continue
                if zone == 'top':
                    end_top(mb, F, s0, s1, h, f, Z)
                    continue
                glazing(mb, F, s0, s1, 0.0, h, 'Glass light', 'Frame dark', mullions=1, transom=h - 0.25,
                        white_frame=opt.get('white_frame', False))
            elif kind == 'darkglass':
                if zone == 'top' and not opt.get('entrance'):
                    glazing(mb, F, s0, s1, 0.0, h, 'Glass dark', 'Frame dark', mullions=0, transom=h - 0.25)
                    continue
                glazing(mb, F, s0, s1, 0.0, h, 'Glass dark', 'Frame dark', mullions=1 if s1 - s0 > 2 else 0, transom=h - 0.25)
            elif kind == 'pilaster':
                wall(mb, F, s0, s1, 0.0, h, 'Stone white', off=-0.02)
                slab_box(mb, F, s0 + 0.05, s1 - 0.05, -0.02, 0.38, 0.0, h, 'Stone white', top=False)
            elif kind == 'gold':
                if f < 7:
                    wall(mb, F, s0, s1, 0.0, h, 'Brick dark')
                else:
                    wall(mb, F, s0, s1, 0.0, h, 'Stone gold')
            elif kind == 'bay':
                if f < 7:
                    punched(mb, F, s0, s1, h, 'Brick dark', [((s0 + s1) / 2, min(1.1, s1 - s0 - 0.5))], sill, head, stone='Stone dark')
                else:
                    glazing(mb, F, s0, s1, 0.0, h, 'Bay glass', 'Frame dark', mullions=1, transom=1.1, depth=0.1)


def white_top(mb, F, s0, s1, h, f, Z, name, pils, opt):
    """the white top on a brick strip: white stone with the pilasters of the groups standing out
    and narrow windows between the pilasters of a group"""
    mine = sorted(p for p in pils if s0 - 0.01 <= p <= s1 + 0.01)
    # windows between consecutive pilasters (of one group: closer than 2.6 m)
    wins = []
    allp = sorted(pils)
    for p, q in zip(allp, allp[1:]):
        if q - p < 2.7:
            m = (p + q) / 2
            if s0 + 0.2 < m < s1 - 0.2:
                wins.append((m, max(0.55, min(1.25, q - p - 0.95))))
    if not wins and s1 - s0 > 1.6 and not mine:
        wins = [((s0 + s1) / 2, 0.9)]
    punched(mb, F, s0, s1, h, 'Stone white', wins, 0.6, 2.85, frame='Frame dark', stone=None, reveal=0.18)
    for p in mine:
        slab_box(mb, F, p - 0.4, p + 0.4, -0.02, 0.32, 0.0, h, 'Stone white', top=False)


def end_top(mb, F, s0, s1, h, f, Z):
    """the white top of the ends: a white wall with a French window and a balcony in each bay"""
    m = (s0 + s1) / 2
    punched(mb, F, s0, s1, h, 'Stone white', [(m, min(1.3, s1 - s0 - 0.3))], 0.05, 2.6, frame='Frame dark', reveal=0.15)
    # balcony slab and glass rail
    slab_box(mb, F, s0 + 0.05, s1 - 0.05, 0.0, 0.85, -0.05, 0.12, 'Stone white', bottom=True)
    a, b = F.p(s0 + 0.08, 0.83), F.p(s1 - 0.08, 0.83)
    mb.ribbon([a, b], 0.12, 1.1, 'Railing glass', double=True)
    mb.tube([a, b], [1.08, 1.08], [1.13, 1.13], 0.05, 'Frame dark')


def end_fins(mb, F, h, z0=0.0):
    for t in END_FINS:
        s = F.s(t)
        slab_box(mb, F, s - 0.25, s + 0.25, -0.02, 0.95, z0, h, 'Stone white', top=False)


# ---------------------------------------------------------------------------- cornices

def run_cornice(mb, F, layout, z0, z1, out, mat, skip=('pilaster', 'white'), only=None, chamfer=True):
    """a cornice along face F over the strips of its layout (not across the kinds in `skip`)"""
    segs = []
    for t0, t1, kind, opt in layout:
        if kind in skip or (only and kind not in only):
            continue
        s0, s1 = sorted((F.s(t0), F.s(t1)))
        s0, s1 = max(0.0, s0), min(F.L, s1)
        if segs and abs(segs[-1][1] - s0) < 0.02:
            segs[-1][1] = s1
        else:
            segs.append([s0, s1])
    for s0, s1 in segs:
        slab_box(mb, F, s0, s1, -0.1, out, z0, z1, mat, top=True, bottom=True)
        if chamfer:
            # a smaller step under it (the cornice's profile)
            slab_box(mb, F, s0, s1, -0.1, out * 0.55, z0 - 0.14, z0, mat, top=False, bottom=True)


def cornices(mb, block, f):
    """the horizontal bands at the foot of floor f (z = 0 at its level)"""
    Z = zones(block)
    for name, a, b, layout, ax in faces():
        F = Face(a, b, ax)
        top_f = Z['top_end'] if name == 'end' else Z['top']
        if f in Z['cornices'] and name not in ('recess', 'step1', 'step2', 'step3'):
            run_cornice(mb, F, layout, -0.3, 0.42, 0.42, 'Stone gold')
            run_cornice(mb, F, layout, 0.42, 0.52, 0.3, 'Stone gold', chamfer=False)
        if f == Z['top'] and name not in ('end', 'recess', 'court'):
            run_cornice(mb, F, layout, -0.3, 0.42, 0.42, 'Stone white', skip=('bay',))
        if name == 'court':
            # render 2: the brick panels of the courtyard face end in a golden cornice under the white top
            for t0, t1, kind, opt in layout:
                if kind == 'brick' and f == opt.get('top', Z['top']):
                    s0, s1 = sorted((F.s(t0), F.s(t1)))
                    slab_box(mb, F, max(0, s0) - 0.1, min(F.L, s1) + 0.1, -0.1, 0.45, -0.3, 0.45, 'Stone gold', bottom=True)
        if f == Z['top_end'] and name == 'end':
            run_cornice(mb, F, layout, -0.3, 0.42, 0.42, 'Stone white', skip=())
        # over the dark base: a dark stone band where the strips change to brick
        for t0, t1, kind, opt in layout:
            if kind not in ('brick', 'pier', 'gold', 'bay'):
                continue
            base = opt.get('base', 7 if kind in ('gold', 'bay') else 5)
            if f == base:
                s0, s1 = sorted((F.s(t0), F.s(t1)))
                out = 0.3 + opt.get('proud', 0.0)
                slab_box(mb, F, max(0, s0), min(F.L, s1), -0.1, out, -0.25, 0.25, 'Stone dark', bottom=True)
        # the corner bays' golden frames
        if f in Z['bay_frames'] and name in ('step1', 'step2', 'step3'):
            dz = {'step1': 0.0, 'step2': 0.004, 'step3': 0.008}[name]   # (the frames meet at the corners)
            slab_box(mb, F, -0.42, F.L + 0.42, -0.1, 0.42, -0.25 - dz, 0.4 + dz, 'Stone gold', bottom=True)


# ---------------------------------------------------------------------------- meshes

def floor_meshes(block, plan, f, mats, name, MeshBuilder):
    """(slab mesh, walls mesh) of floor f of a slab block, z = 0 at its floor level"""
    h = height(f, block)
    out = outline()
    mb = MeshBuilder()
    mb.prism(out.buffer(-0.3, join_style='mitre'), -0.22, SLAB, 'Stone dark', 'Shop floor', 'Stone dark')
    cornices(mb, block, f)
    slab_mesh = mb.to_mesh(f'{name} slab', mats)
    mb = MeshBuilder()
    floor_facade(mb, block, f, h)
    Z = zones(block)
    if f >= Z['top_end']:
        for nm, a, b, layout, ax in faces():
            if nm == 'end':
                end_fins(mb, Face(a, b, ax), h)
    return slab_mesh, mb.to_mesh(f'{name} walls', mats)


def build_roof(mb, b, plan, zr):
    """roof, roof cornice and parapet, the crown over the wings' pilaster groups and the ends,
    the corner bays' caps, lift machine rooms"""
    out = outline()
    mb.prism(out.buffer(-0.12, join_style='mitre'), zr - 0.25, zr + 0.2, 'Stone white', 'Roof', None)
    # the roof cornice: a projecting white band all round, a parapet over it
    ring = out.buffer(0.5, join_style='mitre').difference(out.buffer(-0.35, join_style='mitre'))
    mb.prism_chamfer(ring, zr - 0.05, zr + 0.85, 'Stone white', 'Stone white', 'Stone white', c=0.04)
    par = out.buffer(0.18, join_style='mitre').difference(out.buffer(-0.3, join_style='mitre'))
    mb.prism(par, zr + 0.85, zr + 1.55, 'Stone white', 'Stone white')
    Z = zones(b)
    for name, a, bb, layout, ax in faces():
        F = Face(a, bb, ax)
        # screens and dark strips run up to the cornice: their tops show on the parapet line
        spec = STREET_TOP if name == 'street' else COURT_TOP if name == 'court' else None
        if spec:
            for (ta, tb), hgt in spec['crown']:
                sa_, sb_ = sorted((F.s(ta), F.s(tb)))
                n = max(2, round((sb_ - sa_) / 1.6) + 1)
                for k in range(n):
                    s = sa_ + (sb_ - sa_) * k / (n - 1)
                    slab_box(mb, F, s - 0.27, s + 0.27, -0.25, 0.32, zr + 0.85, zr + hgt, 'Stone white')
                    slab_box(mb, F, s - 0.34, s + 0.34, -0.3, 0.4, zr + hgt, zr + hgt + 0.18, 'Stone white', bottom=True)
            # the ±9.7 m pilasters end over the roof cornice
            for t0, t1, kind, opt in layout:
                if kind == 'pilaster':
                    s0, s1 = sorted((F.s(t0), F.s(t1)))
                    slab_box(mb, F, s0 + 0.05, s1 - 0.05, -0.02, 0.38, zr + 0.85, zr + 1.9, 'Stone white')
        if name == 'street' or name == 'court':
            # the heavy cornice over the middle section (render 1: deeper and higher than the wings')
            for t0, t1, kind, opt in layout:
                pass
            s0, s1 = sorted((F.s(9.3), F.s(-8.8)))
            if name == 'street':
                slab_box(mb, F, s0, s1, -0.2, 0.85, zr + 0.85, zr + 1.55, 'Stone white', bottom=True)
        if name == 'end':
            for t in END_FINS:
                s = F.s(t)
                slab_box(mb, F, s - 0.25, s + 0.25, -0.02, 0.95, zr - 0.05, zr + 3.4, 'Stone white')
            slab_box(mb, F, F.s(END_FINS[0]) - 0.3 if F.s(END_FINS[0]) < F.s(END_FINS[-1]) else F.s(END_FINS[-1]) - 0.3,
                     max(F.s(END_FINS[0]), F.s(END_FINS[-1])) + 0.3, 0.3, 1.0, zr + 3.0, zr + 3.4, 'Stone white', bottom=True)
        if name in ('step1', 'step2', 'step3'):
            # the corner bays rise past the roof under a white cap
            slab_box(mb, F, 0.0, F.L, -0.1, 0.12, zr + 0.85, zr + 2.2, 'Bay glass')
            slab_box(mb, F, -0.4, F.L + 0.4, -0.3, 0.7, zr + 2.2, zr + 2.65, 'Stone white', bottom=True)
            slab_box(mb, F, -0.3, F.L + 0.3, -0.1, 0.42, zr + 0.6, zr + 1.0, 'Stone gold', bottom=True)
    # lift machine rooms over the stair halls (plan common areas)
    for c in plan['common']:
        g = Polygon(c).buffer(0)
        if g.area < 15:
            continue
        x0, y0, x1, y1 = g.bounds
        w, d = min(x1 - x0 + 1.0, 12.0), min(y1 - y0 + 1.0, 9.0)
        cx, cy = g.centroid.x, g.centroid.y
        mb.box(cx, cy, zr + 0.2, w, d, 3.2, 'Stone white')
        mb.box(cx, cy, zr + 3.4, w + 0.3, d + 0.3, 0.25, 'Stone white')
    # a few condensers
    inner = out.buffer(-1.5, join_style='mitre')
    x0, y0, x1, y1 = inner.bounds
    for k in range(10):
        x = x0 + 3 + (x1 - x0 - 6) * ((k * 0.37) % 1)
        y = y0 + 2 + (y1 - y0 - 4) * ((k * 0.61) % 1)
        if inner.contains(box(x - 0.6, y - 0.4, x + 0.6, y + 0.4)):
            mb.box(x, y, zr + 0.2, 1.2, 0.8, 0.9, 'Metal')
