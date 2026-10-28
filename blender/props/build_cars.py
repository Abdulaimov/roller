"""Three car bodies for the streets and car parks: saloon, SUV and hatchback, modelled here from
typical dimensions (no outside model, so nothing to license). Writes build/cars.glb; blender/export_web.sh
compresses it to public/models/cars.glb.

    blender -b --factory-startup -P blender/props/build_cars.py -- [--out build/cars.glb]

Each body is a loft of cross-sections along the car: the lower body (rounded box whose bottom edge
rises over the wheels into arches) and the glasshouse on top in one ring, so the shape is smooth;
then four tyres with rims, lamps and a dark underbody. Materials (the viewer sets their look):
Car paint, Car glass, Car tyre, Car rim, Car lamp, Car rear lamp, Car under. x = forward, z = up, metres.
"""
import math
import os
import sys

import bpy
import bmesh

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')

# Profiles: (x, value) points along the car; linear in between.
TYPES = {
    'saloon': dict(
        L=4.65, W=1.80, wheel_x=(1.38, -1.37), wheel_r=0.32, track=0.78, ride=0.24,
        belt=[(-2.32, 0.70), (-2.12, 0.92), (-1.85, 0.99), (-1.45, 1.00), (1.05, 0.93), (1.9, 0.83), (2.2, 0.72), (2.32, 0.60)],
        roof=[(-1.45, 1.00), (-0.80, 1.41), (0.30, 1.45), (1.05, 0.93)],
        width=[(-2.32, 1.62), (-2.0, 1.76), (-1.2, 1.80), (1.2, 1.80), (2.0, 1.74), (2.32, 1.56)],
        roof_w=1.22,
    ),
    'suv': dict(
        L=4.70, W=1.90, wheel_x=(1.42, -1.40), wheel_r=0.37, track=0.82, ride=0.34,
        belt=[(-2.35, 0.86), (-2.25, 1.10), (-2.1, 1.14), (1.2, 1.10), (1.95, 1.02), (2.25, 0.92), (2.35, 0.78)],
        roof=[(-2.18, 1.14), (-2.05, 1.70), (0.45, 1.74), (1.2, 1.10)],
        width=[(-2.35, 1.80), (-2.1, 1.88), (2.0, 1.88), (2.35, 1.72)],
        roof_w=1.46,
    ),
    'hatch': dict(
        L=4.15, W=1.78, wheel_x=(1.26, -1.26), wheel_r=0.31, track=0.77, ride=0.24,
        belt=[(-2.07, 0.78), (-1.98, 0.96), (-1.85, 0.99), (0.95, 0.94), (1.75, 0.84), (2.0, 0.72), (2.08, 0.60)],
        roof=[(-1.92, 0.99), (-1.62, 1.44), (0.25, 1.48), (0.95, 0.94)],
        width=[(-2.07, 1.66), (-1.8, 1.76), (1.6, 1.78), (2.08, 1.60)],
        roof_w=1.24,
    ),
}


def interp(pts, x):
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, v0), (x1, v1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            t = t * t * (3 - 2 * t)  # smooth between the control points
            return v0 + (v1 - v0) * t
    return pts[-1][1]


def material(name):
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)


def build(name, T, sections=48, seg=28):
    bm = bmesh.new()
    mats = ['Car paint', 'Car glass', 'Car tyre', 'Car rim', 'Car lamp', 'Car rear lamp', 'Car under']
    me = bpy.data.meshes.new(name)
    for m in mats:
        me.materials.append(material(m))
    M = {m: i for i, m in enumerate(mats)}
    half = T['L'] / 2
    xs = [-half + T['L'] * (i / (sections - 1)) for i in range(sections)]
    rings = []
    roof_x0, roof_x1 = T['roof'][0][0], T['roof'][-1][0]
    for x in xs:
        w = interp(T['width'], x) / 2
        belt = interp(T['belt'], x)
        bottom = T['ride']
        for wx in T['wheel_x']:  # wheel arches: the lower edge rises over each wheel
            d = abs(x - wx) / (T['wheel_r'] + 0.08)
            if d < 1:
                bottom = max(bottom, T['ride'] + (2 * T['wheel_r'] + 0.06 - T['ride']) * math.sqrt(1 - d * d))
        if roof_x0 < x < roof_x1:
            roof = interp(T['roof'], x)
        else:
            roof = belt
        rw = min(w, T['roof_w'] / 2 + (w - T['roof_w'] / 2) * max(0.0, 1 - (roof - belt) / 0.35))
        rb, rt = 0.10, 0.08  # corner radii: lower body, roof
        pts = []
        # around the section, starting low on the left side (y = +w), anticlockwise seen from the front
        pts.append((w - 0.02, bottom, 'body'))
        pts.append((w, bottom + rb, 'body'))
        pts.append((w, belt - 0.12, 'body'))
        pts.append((w - 0.04, belt, 'body'))           # shoulder
        pts.append((rw + 0.04, belt + (roof - belt) * 0.15, 'glass'))
        pts.append((rw, roof - rt, 'glass'))
        pts.append((rw - rt, roof, 'roof'))
        pts.append((-(rw - rt), roof, 'roof'))
        pts.append((-rw, roof - rt, 'roof'))
        pts.append((-(rw + 0.04), belt + (roof - belt) * 0.15, 'glass'))
        pts.append((-(w - 0.04), belt, 'glass'))
        pts.append((-w, belt - 0.12, 'body'))
        pts.append((-w, bottom + rb, 'body'))
        pts.append((-(w - 0.02), bottom, 'body'))
        rings.append([bm.verts.new((x, y, z)) for y, z, _ in pts])
    # side faces between rings; the glasshouse band is glass only where there is a roof above it
    n = len(rings[0])
    for a, b, x in zip(rings, rings[1:], xs[1:]):
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new((a[i], b[i], b[j], a[j]))
            if i == n - 1:
                f.material_index = M['Car under']
            elif i in (3, 4, 8, 9):  # side windows: belt line up to the roof edge (zero height where no roof)
                f.material_index = M['Car glass']
            else:
                f.material_index = M['Car paint']
    # windscreen and rear window: the glasshouse faces that slope fore and aft are glass too
    for f in bm.faces:
        if f.material_index == M['Car paint']:
            c = f.calc_center_median()
            nrm = f.normal
            if c.z > interp(T['belt'], c.x) + 0.04 and abs(nrm.x) > 0.35:
                f.material_index = M['Car glass']
    # ends
    for ring in (rings[0], rings[-1]):
        f = bm.faces.new(ring if ring is rings[-1] else list(reversed(ring)))
        f.material_index = M['Car paint']
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # lamps: thin boxes in the nose and tail
    def box(cx, cy, cz, sx, sy, sz, mat):
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r['verts']:
            v.co.x = cx + v.co.x * sx
            v.co.y = cy + v.co.y * sy
            v.co.z = cz + v.co.z * sz
        for f in {f for v in r['verts'] for f in v.link_faces}:
            f.material_index = M[mat]
    xf, xr = half - 0.05, -half + 0.05
    zf = interp(T['belt'], xf) - 0.12
    zr = interp(T['belt'], xr) - 0.12
    for s in (1, -1):
        box(xf, s * (interp(T['width'], xf) / 2 - 0.28), zf, 0.12, 0.36, 0.09, 'Car lamp')
        box(xr, s * (interp(T['width'], xr) / 2 - 0.25), zr, 0.10, 0.34, 0.10, 'Car rear lamp')
    # underbody
    box(0, 0, T['ride'] + 0.02, T['L'] * 0.86, T['W'] * 0.86, 0.04, 'Car under')
    # wheels
    for wx in T['wheel_x']:
        for s in (1, -1):
            r = T['wheel_r']
            y_out, y_in = s * (T['track'] + 0.11), s * (T['track'] - 0.11)
            ring = lambda y, rad: [bm.verts.new((wx + rad * math.cos(2 * math.pi * k / seg), y, r + rad * math.sin(2 * math.pi * k / seg))) for k in range(seg)]
            o_tread, i_tread = ring(y_out - s * 0.02, r), ring(y_in, r)
            o_side = ring(y_out, r * 0.86)
            rim = ring(y_out - s * 0.035, r * 0.62)
            for k in range(seg):
                kk = (k + 1) % seg
                fs = [bm.faces.new((o_tread[k], o_tread[kk], i_tread[kk], i_tread[k])),
                      bm.faces.new((o_side[k], o_side[kk], o_tread[kk], o_tread[k])),
                      bm.faces.new((rim[k], rim[kk], o_side[kk], o_side[k]))]
                for f in fs:
                    f.material_index = M['Car tyre']
            f = bm.faces.new(rim if s < 0 else list(reversed(rim)))
            f.material_index = M['Car rim']
            f = bm.faces.new(i_tread if s > 0 else list(reversed(i_tread)))
            f.material_index = M['Car tyre']
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(40))
    except AttributeError:
        pass
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = argv[argv.index('--out') + 1] if '--out' in argv else os.path.join(ROOT, 'build', 'cars.glb')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for name, T in TYPES.items():
        build(name, T)                                  # close up
        build(name + '_far', T, sections=14, seg=10)   # beyond ~120 m: a quarter of the triangles
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_apply=True, export_cameras=False,
                              export_lights=False, export_yup=True)
    print('wrote', out)


if __name__ == '__main__':
    main()
