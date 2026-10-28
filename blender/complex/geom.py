"""Small mesh-building toolkit on top of bpy + shapely.

All plan geometry is built with shapely in metres (x = east, y = north) and
turned into Blender meshes here. A MeshBuilder collects faces with a material
slot each, so one object can carry several materials.
"""
import math

import bpy
import numpy as np
import shapely
from shapely.geometry import Polygon


# ----------------------------------------------------------------------------
# 2D helpers
# ----------------------------------------------------------------------------

def arc_pts(cx, cy, r, a0, a1, step=math.radians(6)):
    n = max(2, int(math.ceil(abs(a1 - a0) / step)))
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def rounded_rect(x0, y0, x1, y1, r_sw, r_se, r_ne, r_nw):
    """Axis-aligned rectangle with an individual radius per corner."""
    pts = []
    pts += arc_pts(x1 - r_se, y0 + r_se, r_se, -math.pi / 2, 0) if r_se > 0 else [(x1, y0)]
    pts += arc_pts(x1 - r_ne, y1 - r_ne, r_ne, 0, math.pi / 2) if r_ne > 0 else [(x1, y1)]
    pts += arc_pts(x0 + r_nw, y1 - r_nw, r_nw, math.pi / 2, math.pi) if r_nw > 0 else [(x0, y1)]
    pts += arc_pts(x0 + r_sw, y0 + r_sw, r_sw, math.pi, 1.5 * math.pi) if r_sw > 0 else [(x0, y0)]
    return Polygon(pts).buffer(0)


def biggest(geom):
    """Largest polygon of a (multi)polygon result."""
    if hasattr(geom, 'geoms'):
        polys = [g for g in geom.geoms if g.geom_type == 'Polygon']
        return max(polys, key=lambda g: g.area) if polys else Polygon()
    return geom


def ccw(poly):
    return shapely.geometry.polygon.orient(poly, 1.0)


def ring_coords(poly):
    """Exterior ring as a list of (x, y) without the closing duplicate, counter-clockwise."""
    c = list(ccw(poly).exterior.coords)
    return c[:-1]


def simplify_ring(pts, tol=0.02):
    """Drop nearly collinear vertices so long straight walls stay a single quad."""
    out = []
    n = len(pts)
    for i in range(n):
        a, b, c = np.array(pts[i - 1]), np.array(pts[i]), np.array(pts[(i + 1) % n])
        ab, bc = b - a, c - b
        if np.linalg.norm(ab) < 1e-4:
            continue
        cross = abs(ab[0] * bc[1] - ab[1] * bc[0]) / (np.linalg.norm(ab) * max(np.linalg.norm(bc), 1e-6))
        if cross > tol:
            out.append(pts[i])
    return out


def resample(pts, step, closed=True):
    """Points along a polyline every `step` metres (keeps the original corners)."""
    out = []
    seq = list(pts) + ([pts[0]] if closed else [])
    for a, b in zip(seq[:-1], seq[1:]):
        a, b = np.array(a, float), np.array(b, float)
        L = np.linalg.norm(b - a)
        n = max(1, int(round(L / step)))
        for i in range(n):
            out.append(tuple(a + (b - a) * i / n))
    if not closed:
        out.append(tuple(seq[-1]))
    return out


def transform2(pts, origin, rot_deg):
    c, s = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))
    ox, oy = origin
    return [(ox + c * x - s * y, oy + s * x + c * y) for x, y in pts]


def place(poly, origin, rot_deg):
    return shapely.affinity.translate(shapely.affinity.rotate(poly, rot_deg, origin=(0, 0)), *origin)


# ----------------------------------------------------------------------------
# Mesh builder
# ----------------------------------------------------------------------------

class MeshBuilder:
    def __init__(self):
        self.verts = []
        self.faces = []
        self.mats = []
        self.uvs = []  # per face list of (u, v)
        self._vmap = {}

    def _v(self, p):
        key = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
        i = self._vmap.get(key)
        if i is None:
            i = len(self.verts)
            self.verts.append(key)
            self._vmap[key] = i
        return i

    def face(self, pts, mat, uv=None):
        idx = [self._v(p) for p in pts]
        # drop consecutive duplicates
        clean = [i for k, i in enumerate(idx) if i != idx[k - 1]]
        if len(set(clean)) < 3:
            return
        self.faces.append(clean)
        self.mats.append(mat)
        self.uvs.append(uv if uv is not None and len(uv) == len(clean) else None)

    # --- primitives ---------------------------------------------------------
    def quad_wall(self, a, b, z0, z1, mat, flip=False, u0=0.0):
        """Vertical quad from 2D point a to b. Outward normal is to the right of a->b
        for counter-clockwise rings, i.e. (dy, -dx). UVs are metres: u along the wall from u0
        (pass the running length along a ring so textures run on without seams), v = height."""
        L = math.dist(a, b)
        pts = [(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)]
        uv = [(u0, z0), (u0 + L, z0), (u0 + L, z1), (u0, z1)]
        if flip:
            pts.reverse()
            uv.reverse()
        self.face(pts, mat, uv)

    def polygon_face(self, poly, z, mat, up=True):
        """Horizontal face for a shapely polygon (holes supported via triangulation)."""
        if hasattr(poly, 'geoms'):
            for g in poly.geoms:
                if g.geom_type == 'Polygon':
                    self.polygon_face(g, z, mat, up)
            return
        if poly.is_empty or poly.geom_type != 'Polygon':
            return
        poly = ccw(poly)
        if len(poly.interiors) == 0:
            pts = [(x, y, z) for x, y in ring_coords(poly)]
            uv = [(x, y) for x, y, _ in pts]
            if not up:
                pts.reverse()
                uv.reverse()
            self.face(pts, mat, uv)
            return
        tris = shapely.constrained_delaunay_triangles(poly)
        for t in tris.geoms:
            c = list(ccw(t).exterior.coords)[:-1]
            pts = [(x, y, z) for x, y in c]
            uv = [(x, y) for x, y in c]
            if not up:
                pts.reverse()
                uv.reverse()
            self.face(pts, mat, uv)

    def prism(self, poly, z0, z1, side, top=None, bottom=None):
        if poly.is_empty:
            return
        if hasattr(poly, 'geoms'):
            for g in poly.geoms:
                if g.geom_type in ('Polygon', 'MultiPolygon'):
                    self.prism(g, z0, z1, side, top, bottom)
            return
        if poly.geom_type != 'Polygon':
            return
        poly = ccw(poly)
        for ring, outer in [(poly.exterior, True)] + [(r, False) for r in poly.interiors]:
            c = list(ring.coords)[:-1]
            u = 0.0
            for a, b in zip(c, c[1:] + c[:1]):
                self.quad_wall(a, b, z0, z1, side, flip=False, u0=u)
                u += math.dist(a, b)
        if top is not None:
            self.polygon_face(poly, z1, top, up=True)
        if bottom is not None:
            self.polygon_face(poly, z0, bottom, up=False)

    def prism_chamfer(self, poly, z0, z1, side, top=None, bottom=None, c=0.025):
        """Prism whose top and bottom edges are chamfered by c (a slab edge that catches the light
        instead of a knife edge). Falls back to a plain prism for polygons with holes."""
        if poly.is_empty:
            return
        if hasattr(poly, 'geoms'):
            for g in poly.geoms:
                if g.geom_type == 'Polygon':
                    self.prism_chamfer(g, z0, z1, side, top, bottom, c)
            return
        if poly.geom_type != 'Polygon' or poly.interiors or z1 - z0 < 3 * c:
            return self.prism(poly, z0, z1, side, top, bottom)
        ring = [p for p in ring_coords(poly)]
        P = np.array(ring, float)
        n = len(P)
        d = np.roll(P, -1, axis=0) - P
        L = np.linalg.norm(d, axis=1)
        keep = L > 1e-6
        if not keep.all():
            P, n = P[keep], int(keep.sum())
            d = np.roll(P, -1, axis=0) - P
            L = np.linalg.norm(d, axis=1)
        out = np.stack([d[:, 1], -d[:, 0]], axis=1) / L[:, None]
        prev = np.roll(out, 1, axis=0)
        bis = out + prev
        bis /= np.maximum(np.linalg.norm(bis, axis=1), 1e-9)[:, None]
        k = c / np.maximum((bis * out).sum(axis=1), 0.35)
        I = P - bis * k[:, None]
        u = 0.0
        for i in range(n):
            j = (i + 1) % n
            a, b, ai, bi = tuple(P[i]), tuple(P[j]), tuple(I[i]), tuple(I[j])
            u1 = u + float(L[i])
            self.quad_wall(a, b, z0 + c, z1 - c, side, u0=u)
            self.face([(*a, z1 - c), (*b, z1 - c), (*bi, z1), (*ai, z1)], side, [(u, z1 - c), (u1, z1 - c), (u1, z1), (u, z1)])
            self.face([(*ai, z0), (*bi, z0), (*b, z0 + c), (*a, z0 + c)], side, [(u, z0), (u1, z0), (u1, z0 + c), (u, z0 + c)])
            u = u1
        cap = Polygon([tuple(q) for q in I]).buffer(0)
        if top is not None:
            self.polygon_face(cap, z1, top, up=True)
        if bottom is not None:
            self.polygon_face(cap, z0, bottom, up=False)

    def ribbon(self, pts, z0, z1, mat, closed=False, double=False):
        seq = list(pts) + ([pts[0]] if closed else [])
        u = 0.0
        for a, b in zip(seq[:-1], seq[1:]):
            self.quad_wall(a, b, z0, z1, mat, u0=u)
            if double:
                self.quad_wall(a, b, z0, z1, mat, flip=True, u0=u)
            u += math.dist(a, b)

    def ribbon_z(self, pts, zfun0, zfun1, mat, double=False):
        """Ribbon whose bottom/top heights vary per point (lists of z)."""
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            q = [(a[0], a[1], zfun0[i]), (b[0], b[1], zfun0[i + 1]), (b[0], b[1], zfun1[i + 1]), (a[0], a[1], zfun1[i])]
            self.face(q, mat)
            if double:
                self.face(q[::-1], mat)

    def tube(self, pts, z0s, z1s, width, mat, closed=False):
        """Rectangular section band following a polyline (e.g. crown ring)."""
        n = len(pts)
        P = np.array(pts, float)
        normals = []
        for i in range(n):
            if closed:
                d = P[(i + 1) % n] - P[i - 1]
            else:
                d = P[min(i + 1, n - 1)] - P[max(i - 1, 0)]
            d = d / (np.linalg.norm(d) + 1e-9)
            normals.append(np.array([d[1], -d[0]]))
        outer = [tuple(P[i] + normals[i] * width / 2) for i in range(n)]
        inner = [tuple(P[i] - normals[i] * width / 2) for i in range(n)]
        rng = range(n if closed else n - 1)
        u = 0.0
        for i in rng:
            j = (i + 1) % n
            o0, o1, i0, i1 = outer[i], outer[j], inner[i], inner[j]
            a0, a1, b0, b1 = z0s[i], z0s[j], z1s[i], z1s[j]
            L = math.dist(pts[i], pts[j])
            u1 = u + L
            w = width
            self.face([(*o0, a0), (*o1, a1), (*o1, b1), (*o0, b0)], mat, [(u, a0), (u1, a1), (u1, b1), (u, b0)])
            self.face([(*i1, a1), (*i0, a0), (*i0, b0), (*i1, b1)], mat, [(u1, a1), (u, a0), (u, b0), (u1, b1)])
            self.face([(*o0, b0), (*o1, b1), (*i1, b1), (*i0, b0)], mat, [(u, 0), (u1, 0), (u1, w), (u, w)])
            self.face([(*i0, a0), (*i1, a1), (*o1, a1), (*o0, a0)], mat, [(u, w), (u1, w), (u1, 0), (u, 0)])
            u = u1
        if not closed:
            for k, sgn in [(0, 1), (n - 1, -1)]:
                q = [(*outer[k], z0s[k]), (*outer[k], z1s[k]), (*inner[k], z1s[k]), (*inner[k], z0s[k])]
                self.face(q if sgn > 0 else q[::-1], mat)

    def box(self, cx, cy, z0, sx, sy, sz, mat, rot=0.0, top=True, bottom=False):
        """Oriented box; rot in radians about z."""
        c, s = math.cos(rot), math.sin(rot)
        hx, hy = sx / 2, sy / 2
        corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
        pts = [(cx + c * x - s * y, cy + s * x + c * y) for x, y in corners]
        poly = Polygon(pts)
        self.prism(poly, z0, z0 + sz, mat, mat if top else None, mat if bottom else None)

    def panel(self, a, b, z0, z1, mat, offset=0.0, double=False):
        """Flat vertical panel between 2D points a and b pushed `offset` along the outward normal."""
        d = np.array(b, float) - np.array(a, float)
        L = np.linalg.norm(d)
        n = np.array([d[1], -d[0]]) / (L + 1e-9)
        a2 = tuple(np.array(a) + n * offset)
        b2 = tuple(np.array(b) + n * offset)
        self.quad_wall(a2, b2, z0, z1, mat)
        if double:
            self.quad_wall(a2, b2, z0, z1, mat, flip=True)

    def blob(self, cx, cy, cz, rx, ry, rz, mat, subdiv=1, jitter=0.0, rnd=None):
        """Low-poly icosphere (tree crowns, shrubs)."""
        verts, faces = icosphere(subdiv)
        pts = []
        for v in verts:
            j = 1.0 + (rnd.uniform(-jitter, jitter) if rnd and jitter else 0.0)
            pts.append((cx + v[0] * rx * j, cy + v[1] * ry * j, cz + v[2] * rz * j))
        for f in faces:
            self.face([pts[i] for i in f], mat)

    def merge(self, other):
        for f, m, uv in zip(other.faces, other.mats, other.uvs):
            self.face([other.verts[i] for i in f], m, uv)

    # --- output -------------------------------------------------------------
    def to_mesh(self, name, materials):
        """materials: list of bpy materials; face mats index into this list."""
        me = bpy.data.meshes.new(name)
        if not self.faces:
            return me
        used = sorted(set(self.mats))
        slot = {m: i for i, m in enumerate(used)}
        me.from_pydata(self.verts, [], self.faces)
        for m in used:
            me.materials.append(materials[m])
        idx = [slot[m] for m in self.mats]
        me.polygons.foreach_set('material_index', idx)
        uvl = me.uv_layers.new(name='UVMap')
        data = []
        for f, uv in zip(self.faces, self.uvs):
            if uv is None:
                uv = [(0.0, 0.0)] * len(f)
            data.extend(uv)
        flat = [c for uv in data for c in uv]
        uvl.data.foreach_set('uv', flat)
        me.validate(clean_customdata=False)
        me.update()
        smooth_by_angle(me)
        return me


# Trees for the web viewer: while this is a list, the tree helpers record
# each tree here as [x, y, z, height, crown radius, kind] and model it into a builder that is thrown
# away (so the random sequence, and every placement after it, stays as it was); the viewer draws them
# from photographed trees. None: the trees are modelled into the scene (Blender stills).
TREE_LOG = None


def log_tree(mb, x, y, z, h, r, kind):
    """Record the tree when collecting; returns the builder to model it into (a scratch one then)."""
    if TREE_LOG is None:
        return mb
    TREE_LOG.append([round(x, 2), round(y, 2), round(z, 2), round(h, 2), round(r, 2), kind])
    return MeshBuilder()


SMOOTH_ANGLE = math.radians(32)


def smooth_by_angle(me, angle=SMOOTH_ANGLE):
    """Smooth shading across the facets of curved walls, slabs and rails (their faces meet at a few
    degrees), crisp edges where faces meet at more than `angle` (corners, reveals, slab edges)."""
    if not me.polygons:
        return
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    try:
        me.set_sharp_from_angle(angle=angle)   # Blender 4.1+
    except AttributeError:
        me.use_auto_smooth = True               # Blender < 4.1
        me.auto_smooth_angle = angle


_ICO = {}


def icosphere(subdiv=1):
    if subdiv in _ICO:
        return _ICO[subdiv]
    t = (1 + 5 ** 0.5) / 2
    verts = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
             (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    verts = [tuple(c / math.sqrt(sum(x * x for x in v)) for c in v) for v in verts]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
             (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(subdiv):
        cache = {}
        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                p = [(verts[a][i] + verts[b][i]) / 2 for i in range(3)]
                n = math.sqrt(sum(c * c for c in p))
                verts.append(tuple(c / n for c in p))
                cache[key] = len(verts) - 1
            return cache[key]
        nf = []
        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = nf
    _ICO[subdiv] = (verts, faces)
    return _ICO[subdiv]


def make_object(name, mesh, collection, location=(0, 0, 0)):
    ob = bpy.data.objects.new(name, mesh)
    ob.location = location
    collection.objects.link(ob)
    return ob


def get_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col
