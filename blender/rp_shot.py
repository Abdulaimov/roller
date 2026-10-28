"""Render saved build views: blender -b build/rp/rp.blend -P blender/rp_shot.py -- OUT VIEW [x y z tx ty tz lens]"""
import sys, bpy
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:]
sc = bpy.context.scene
if len(a) > 2:
    x, y, z, tx, ty, tz, lens = map(float, a[2:9])
    cam = sc.objects.get('custom') or bpy.data.objects.new('custom', bpy.data.cameras.new('custom'))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.location = (x, y, z)
    cam.rotation_euler = (Vector((tx, ty, tz)) - Vector((x, y, z))).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    cam.data.clip_end = 5000
    sc.camera = cam
else:
    sc.camera = sc.objects[a[1]]
sc.render.resolution_x, sc.render.resolution_y = 1400, 900
sc.render.filepath = a[0]
bpy.ops.render.render(write_still=True)
