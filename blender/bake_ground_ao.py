"""The ground's sky occlusion, baked with Cycles (the viewer's high quality, src/materials.js GROUND_AO):
how much of the sky each point of the ground sees, with the blocks, the podiums, the school, the
kindergarten, the hedges, the trees' crowns, the cars and the play equipment round it. The viewer
darkens the sky's light on the ground by it: the soft contact shade at the foot of the walls, under
the trees and the cars, in the narrow passages — what makes a rendering sit on its ground.
    Blender -b build/ab.blend -P blender/bake_ground_ao.py -- [--ppm 8] [--samples 64] [--dist 14]
    tools/ab/py -c "import numpy as n; from PIL import Image; Image.fromarray(n.load('build/ground_ao.npy'), 'L').save('public/models/ground_ao.webp', quality=90, method=6)"
-> public/models/ground_ao.webp (grey, 1 = open sky) and ground_ao.json (its box in scene metres)
"""
import json
import math
import os
import sys

import bpy
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = lambda k, d: type(d)(argv[argv.index(k) + 1]) if k in argv else d
PPM, SAMPLES, DIST = opt('--ppm', 8.0), opt('--samples', 64), opt('--dist', 14.0)

walk = json.load(open(os.path.join(ROOT, 'public/models/site_walk.json')))
info = json.load(open(os.path.join(ROOT, 'src/model/complex.json')))
x0, y0, nx, ny = walk['x0'], walk['y0'], walk['nx'], walk['ny']
W, H = int(nx * PPM), int(ny * PPM)
sc = bpy.context.scene

# no picking volumes, no night lights
for o in list(bpy.data.objects):
    if o.name.startswith('pick') or o.type in ('CAMERA', 'LIGHT'):
        bpy.data.objects.remove(o, do_unlink=True)

# the trees' crowns and trunks, the cars: they are drawn by the viewer, not in the model
col = bpy.data.collections.new('AO extras')
sc.collection.children.link(col)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0)
crown = bpy.context.object.data
bpy.data.objects.remove(bpy.context.object, do_unlink=True)
bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=1.0, depth=1.0)
trunk = bpy.context.object.data
bpy.data.objects.remove(bpy.context.object, do_unlink=True)
bpy.ops.mesh.primitive_cube_add(size=1.0)
cube = bpy.context.object.data
bpy.data.objects.remove(bpy.context.object, do_unlink=True)


def add(mesh, loc, scale, rot=0.0):
    o = bpy.data.objects.new('ao', mesh)
    col.objects.link(o)
    o.location, o.scale, o.rotation_euler = loc, scale, (0, 0, rot)


n = 0
for t in info['trees_placed']:
    x, y, z, h, r = t[:5]
    kind = t[5] if len(t) > 5 else 'broad'
    if not (x0 < x < x0 + nx and y0 < y < y0 + ny) or z > 1.0:
        continue
    if kind == 'shrub':
        add(crown, (x, y, z + h * 0.45), (r * 0.8, r * 0.8, h * 0.5))
    else:
        # a porous crown: smaller than the leaves reach (the sky shows through them)
        cr = max(0.8, r * 0.62)
        add(crown, (x, y, z + h * 0.62), (cr, cr, max(cr, h * 0.3)))
        add(trunk, (x, y, z + h * 0.25), (0.18, 0.18, h * 0.5))
    n += 1
for c in info['cars']:
    x, y, z, rot = c[:4]
    add(cube, (x, y, z + 0.95), (4.3, 1.75, 1.3), rot)   # a car's body over its wheels (clearance under it)
print('AO extras: trees', n, 'cars', len(info['cars']))

# the receiving plane over the ground (just above the paving and the lawns)
bpy.ops.mesh.primitive_plane_add(size=1.0)
plane = bpy.context.object
plane.name = 'AO plane'
plane.scale = (nx, ny, 1)
plane.location = (x0 + nx / 2, y0 + ny / 2, 0.3)   # over the kerbs' and the beds' tops
bpy.ops.object.transform_apply(scale=True)
img = bpy.data.images.new('ground_ao', W, H, float_buffer=True, is_data=True)
m = bpy.data.materials.new('AO bake')
m.use_nodes = True
tex = m.node_tree.nodes.new('ShaderNodeTexImage')
tex.image = img
m.node_tree.nodes.active = tex
plane.data.materials.append(m)
plane.visible_shadow = False
plane.visible_diffuse = False
plane.visible_glossy = False

sc.render.engine = 'CYCLES'
prefs = bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    sc.cycles.device = 'GPU'
except Exception as e:
    print('GPU unavailable, CPU', e)
sc.cycles.samples = SAMPLES
sc.world.light_settings.distance = DIST
sc.render.bake.margin = 2
for o in bpy.context.view_layer.objects:
    o.select_set(False)
plane.select_set(True)
bpy.context.view_layer.objects.active = plane
bpy.ops.object.bake(type='AO')

a = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)[:, :, 0]   # bottom row first = south
out = np.clip(a, 0, 1)
# from the plane's UV (x east, v north) to the viewer's texture (u = scene x, v = scene z = -north)
out = out[::-1, :]
# (Blender's Python has no imaging library: the array goes out, tools/ab/py writes the WebP)
np.save(os.path.join(ROOT, 'build/ground_ao.npy'), (out * 255 + 0.5).astype(np.uint8))
json.dump({'x0': x0, 'z0': -(y0 + ny), 'w': nx, 'd': ny, 'ppm': PPM, 'samples': SAMPLES, 'dist': DIST},
          open(os.path.join(ROOT, 'public/models/ground_ao.json'), 'w'))
print('ground AO', W, H, 'mean', round(float(out.mean()), 3), 'min', round(float(out.min()), 3))
